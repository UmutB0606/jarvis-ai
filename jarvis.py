import asyncio
import pyaudio
import subprocess
import os
import webbrowser
import base64
import pyautogui
import time
import json
import threading
import psutil
import datetime
from google import genai
from google.genai import types

# === AYARLAR ===
from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
SEHIR = os.getenv("SEHIR", "Ankara")

# === SES AYARLARI ===
CHUNK = 2048
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

# === HAFIZA ===
HAFIZA_DOSYA = "jarvis_hafiza.json"

def hafiza_yukle():
    if os.path.exists(HAFIZA_DOSYA):
        with open(HAFIZA_DOSYA, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"notlar": [], "hatirlaticilar": []}

def hafiza_kaydet(hafiza):
    with open(HAFIZA_DOSYA, "w", encoding="utf-8") as f:
        json.dump(hafiza, f, ensure_ascii=False, indent=2)

hafiza = hafiza_yukle()

# === KAMERA MODU ===
kamera_aktif = False
kamera_thread = None

def kamera_modu_baslat(session_ref):
    global kamera_aktif
    import cv2
    import mediapipe as mp

    mp_hands = mp.solutions.hands
    mp_face_mesh = mp.solutions.face_mesh

    cap = cv2.VideoCapture(0)
    son_komut_zamani = 0
    komut_bekleme = 2  # saniye

    print("📷 Kamera modu aktif!")

    with mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7) as hands, \
         mp_face_mesh.FaceMesh(min_detection_confidence=0.7) as face_mesh:

        onceki_burun_y = None

        while kamera_aktif:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            simdi = time.time()

            # El tespiti
            el_sonuc = hands.process(rgb)
            yuz_sonuc = face_mesh.process(rgb)

            komut = None

            if el_sonuc.multi_hand_landmarks and (simdi - son_komut_zamani) > komut_bekleme:
                el = el_sonuc.multi_hand_landmarks[0]
                landmarks = el.landmark

                # Parmak uçları
                parmak_uclari = [4, 8, 12, 16, 20]
                parmak_eklemleri = [3, 6, 10, 14, 18]

                acik_parmaklar = []
                for uc, eklem in zip(parmak_uclari[1:], parmak_eklemleri[1:]):
                    if landmarks[uc].y < landmarks[eklem].y:
                        acik_parmaklar.append(True)
                    else:
                        acik_parmaklar.append(False)

                # Başparmak
                if landmarks[4].x < landmarks[3].x:
                    basparmak_acik = True
                else:
                    basparmak_acik = False

                acik_sayi = sum(acik_parmaklar)

                # Hareketler
                if acik_sayi == 4 and basparmak_acik:  # ✋ Açık el
                    komut = "muzik_duraklat"
                    print("✋ Müzik duraklat/devam")
                elif acik_sayi == 0 and basparmak_acik:  # 👍 Beğen
                    komut = "ses_artir"
                    print("👍 Ses artır")
                elif acik_sayi == 0 and not basparmak_acik:  # 👊 Yumruk
                    komut = "onceki_sarki"
                    print("👊 Önceki şarkı")
                elif acik_sayi == 1 and acik_parmaklar[0]:  # ☝️ Bir parmak
                    komut = "sonraki_sarki"
                    print("✌️ Sonraki şarkı")
                elif acik_sayi == 2 and acik_parmaklar[0] and acik_parmaklar[1]:  # ✌️
                    komut = "sonraki_sarki"
                    print("✌️ Sonraki şarkı")

            # Baş hareketi (yüz mesh)
            if yuz_sonuc.multi_face_landmarks and (simdi - son_komut_zamani) > komut_bekleme:
                yuz = yuz_sonuc.multi_face_landmarks[0]
                burun_y = yuz.landmark[1].y

                if onceki_burun_y is not None:
                    fark = burun_y - onceki_burun_y
                    if fark > 0.03:  # Aşağı → ses azalt
                        komut = "ses_azalt"
                        print("👇 Ses azalt")
                    elif fark < -0.03:  # Yukarı → ses artır
                        komut = "ses_artir"
                        print("👆 Ses artır")

                onceki_burun_y = burun_y

            # Komutu uygula
            if komut:
                son_komut_zamani = simdi
                if komut == "muzik_duraklat":
                    pyautogui.press("playpause")
                elif komut == "ses_artir":
                    for _ in range(3): pyautogui.press("volumeup")
                elif komut == "ses_azalt":
                    for _ in range(3): pyautogui.press("volumedown")
                elif komut == "sonraki_sarki":
                    pyautogui.press("nexttrack")
                elif komut == "onceki_sarki":
                    pyautogui.press("prevtrack")

            # Göster
            cv2.putText(frame, "Kamera Modu Aktif - Jarvis", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow("Jarvis Kamera", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()
    print("📷 Kamera modu kapatıldı.")

# === EKRAN ANALİZİ ===
def ekran_analiz_et_ve_tikla(hedef_aciklama, islem):
    try:
        temp_path = os.path.join(os.environ["USERPROFILE"], "temp_screen.png")
        screenshot = pyautogui.screenshot()
        screenshot.save(temp_path)

        with open(temp_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode()

        ekran_w, ekran_h = pyautogui.size()
        client_temp = genai.Client(api_key=GEMINI_API_KEY)
        response = client_temp.models.generate_content(
            model="gemini-2.5-flash",
            contents=[{
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": "image/png", "data": img_data}},
                    {"text": f"""Ekran boyutu: {ekran_w}x{ekran_h} piksel.
'{hedef_aciklama}' öğesinin tam merkez koordinatını bul.
SADECE X,Y formatında cevap ver. Örnek: 523,847"""}
                ]
            }]
        )

        koordinat = response.text.strip().replace(" ", "").split("\n")[0]
        x, y = map(int, koordinat.split(","))
        print(f"🎯 Koordinat: {x},{y}")
        return x, y

    except Exception as e:
        print(f"⚠️ Ekran analiz hatası: {e}")
        return None, None

# === ARAÇLAR ===
def tool_calistir(fonksiyon_adi, parametreler):
    global kamera_aktif, kamera_thread, hafiza
    print(f"🔧 Komut: {fonksiyon_adi} | {parametreler}")
    try:
        if fonksiyon_adi == "uygulama_ac":
            uygulama = parametreler.get("uygulama", "")
            pyautogui.press("super")
            time.sleep(0.8)
            pyautogui.write(uygulama, interval=0.05)
            time.sleep(0.5)
            pyautogui.press("enter")
            time.sleep(1.5)
            return f"{uygulama} açıldı."

        elif fonksiyon_adi == "web_ara":
            sorgu = parametreler.get("sorgu", "")
            url = f"https://www.google.com/search?q={sorgu.replace(' ', '+')}&btnI"
            webbrowser.open(url)
            time.sleep(2)
            return f"{sorgu} açıldı."

        elif fonksiyon_adi == "ekranda_bul_tikla":
            hedef = parametreler.get("hedef", "")
            time.sleep(0.5)
            x, y = ekran_analiz_et_ve_tikla(hedef, "tikla")
            if x and y:
                pyautogui.click(x, y)
                time.sleep(0.3)
                return f"{hedef} tıklandı."
            return f"{hedef} bulunamadı."

        elif fonksiyon_adi == "ekranda_bul_yaz":
            hedef = parametreler.get("hedef", "")
            metin = parametreler.get("metin", "")
            time.sleep(0.5)
            x, y = ekran_analiz_et_ve_tikla(hedef, "tikla")
            if x and y:
                pyautogui.click(x, y)
                time.sleep(0.3)
                pyautogui.hotkey("ctrl", "a")
                time.sleep(0.1)
                pyautogui.write(metin, interval=0.05)
                return f"'{metin}' yazıldı."
            return f"{hedef} bulunamadı."

        elif fonksiyon_adi == "yaz":
            metin = parametreler.get("metin", "")
            time.sleep(0.2)
            pyautogui.write(metin, interval=0.05)
            return f"'{metin}' yazıldı."

        elif fonksiyon_adi == "klavye_bas":
            tus = parametreler.get("tus", "")
            pyautogui.press(tus)
            return f"{tus} basıldı."

        elif fonksiyon_adi == "klavye_kisayol":
            tuslar = parametreler.get("tuslar", "")
            tus_listesi = [t.strip() for t in tuslar.split("+")]
            pyautogui.hotkey(*tus_listesi)
            return f"{tuslar} kullanıldı."

        elif fonksiyon_adi == "ses_kontrol":
            islem = parametreler.get("islem", "")
            if islem == "artir":
                for _ in range(5): pyautogui.press("volumeup")
            elif islem == "azalt":
                for _ in range(5): pyautogui.press("volumedown")
            elif islem in ["kapat", "ac"]:
                pyautogui.press("volumemute")
            return f"Ses {islem} yapıldı."

        elif fonksiyon_adi == "bilgisayar_kapat":
            islem = parametreler.get("islem", "kapat")
            if islem == "kapat":
                subprocess.run("shutdown /s /t 5", shell=True)
            elif islem == "yeniden_baslat":
                subprocess.run("shutdown /r /t 5", shell=True)
            elif islem == "iptal":
                subprocess.run("shutdown /a", shell=True)
            return f"Bilgisayar {islem} yapılıyor."

        elif fonksiyon_adi == "uyku_zamanlayici":
            dakika = parametreler.get("dakika", 30)
            saniye = dakika * 60
            subprocess.run(f"shutdown /s /t {saniye}", shell=True)
            return f"{dakika} dakika sonra bilgisayar kapanacak."

        elif fonksiyon_adi == "sistem_durumu":
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            battery = psutil.sensors_battery()
            batarya = f"{battery.percent:.0f}%" if battery else "Yok"
            return (f"CPU: {cpu}% | "
                   f"RAM: {ram.percent}% ({ram.used // 1024**3}GB / {ram.total // 1024**3}GB) | "
                   f"Disk: {disk.percent}% | "
                   f"Batarya: {batarya}")

        elif fonksiyon_adi == "hava_durumu":
            import urllib.request
            sehir = parametreler.get("sehir", SEHIR)
            url = f"https://api.openweathermap.org/data/2.5/weather?q={sehir}&appid={WEATHER_API_KEY}&units=metric&lang=tr"
            with urllib.request.urlopen(url) as response:
                veri = json.loads(response.read())
            sicaklik = veri["main"]["temp"]
            hissedilen = veri["main"]["feels_like"]
            durum = veri["weather"][0]["description"]
            nem = veri["main"]["humidity"]
            return f"{sehir}: {sicaklik:.0f}°C, hissedilen {hissedilen:.0f}°C, {durum}, nem %{nem}"

        elif fonksiyon_adi == "not_ekle":
            not_metni = parametreler.get("not", "")
            hafiza["notlar"].append({
                "metin": not_metni,
                "zaman": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            })
            hafiza_kaydet(hafiza)
            return f"Not kaydedildi: {not_metni}"

        elif fonksiyon_adi == "notlari_goster":
            if not hafiza["notlar"]:
                return "Hiç not yok."
            notlar = [f"{n['zaman']}: {n['metin']}" for n in hafiza["notlar"][-5:]]
            return "Son notlar: " + " | ".join(notlar)

        elif fonksiyon_adi == "not_sil":
            hafiza["notlar"] = []
            hafiza_kaydet(hafiza)
            return "Tüm notlar silindi."

        elif fonksiyon_adi == "kamera_mod":
            islem = parametreler.get("islem", "ac")
            if islem == "ac" and not kamera_aktif:
                kamera_aktif = True
                kamera_thread = threading.Thread(target=kamera_modu_baslat, args=(None,), daemon=True)
                kamera_thread.start()
                return "Kamera modu açıldı. El hareketleriyle kontrol edebilirsiniz."
            elif islem == "kapat" and kamera_aktif:
                kamera_aktif = False
                return "Kamera modu kapatıldı."
            return "Kamera modu zaten o durumda."

        elif fonksiyon_adi == "klasor_ac":
            klasor = parametreler.get("klasor", "").lower()
            klasorler = {
                "masaustu": os.path.join(os.environ["USERPROFILE"], "Desktop"),
                "masaüstü": os.path.join(os.environ["USERPROFILE"], "Desktop"),
                "belgeler": os.path.join(os.environ["USERPROFILE"], "Documents"),
                "indirilenler": os.path.join(os.environ["USERPROFILE"], "Downloads"),
                "resimler": os.path.join(os.environ["USERPROFILE"], "Pictures"),
                "muzik": os.path.join(os.environ["USERPROFILE"], "Music"),
                "müzik": os.path.join(os.environ["USERPROFILE"], "Music"),
            }
            hedef = klasorler.get(klasor, os.path.join(os.environ["USERPROFILE"], "Desktop"))
            subprocess.Popen(f'explorer "{hedef}"')
            return f"{klasor} açıldı."

        elif fonksiyon_adi == "ekran_goruntusu":
            dosya_adi = f"ekran_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            hedef = os.path.join(os.environ["USERPROFILE"], "Desktop", dosya_adi)
            pyautogui.screenshot(hedef)
            return "Ekran görüntüsü masaüstüne kaydedildi."

    except Exception as e:
        print(f"⚠️ Tool hatası: {e}")
        return "Komut çalıştırılamadı."
    return "İşlem tamamlandı."

TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="uygulama_ac",
            description="Windows aramasıyla herhangi bir uygulamayı açar.",
            parameters=types.Schema(type="OBJECT", properties={"uygulama": types.Schema(type="STRING")}, required=["uygulama"])
        ),
        types.FunctionDeclaration(
            name="web_ara",
            description="Google'da arama yapar ve ilk sonucu açar. YouTube için sorguya 'youtube' ekle.",
            parameters=types.Schema(type="OBJECT", properties={"sorgu": types.Schema(type="STRING")}, required=["sorgu"])
        ),
        types.FunctionDeclaration(
            name="ekranda_bul_tikla",
            description="Ekranda görsel olarak bir öğeyi bulup tıklar.",
            parameters=types.Schema(type="OBJECT", properties={"hedef": types.Schema(type="STRING", description="Tıklanacak öğenin detaylı açıklaması")}, required=["hedef"])
        ),
        types.FunctionDeclaration(
            name="ekranda_bul_yaz",
            description="Ekranda bir kutuyu bulup metin yazar.",
            parameters=types.Schema(type="OBJECT", properties={
                "hedef": types.Schema(type="STRING"),
                "metin": types.Schema(type="STRING")
            }, required=["hedef", "metin"])
        ),
        types.FunctionDeclaration(
            name="yaz",
            description="Aktif alana metin yazar.",
            parameters=types.Schema(type="OBJECT", properties={"metin": types.Schema(type="STRING")}, required=["metin"])
        ),
        types.FunctionDeclaration(
            name="klavye_bas",
            description="Klavye tuşuna basar. enter, escape, space, tab, f5 gibi.",
            parameters=types.Schema(type="OBJECT", properties={"tus": types.Schema(type="STRING")}, required=["tus"])
        ),
        types.FunctionDeclaration(
            name="klavye_kisayol",
            description="Klavye kısayolu kullanır. ctrl+c, ctrl+v, alt+f4 gibi.",
            parameters=types.Schema(type="OBJECT", properties={"tuslar": types.Schema(type="STRING")}, required=["tuslar"])
        ),
        types.FunctionDeclaration(
            name="ses_kontrol",
            description="Ses seviyesini kontrol eder.",
            parameters=types.Schema(type="OBJECT", properties={"islem": types.Schema(type="STRING", description="artir, azalt, kapat veya ac")}, required=["islem"])
        ),
        types.FunctionDeclaration(
            name="bilgisayar_kapat",
            description="Bilgisayarı kapatır veya yeniden başlatır.",
            parameters=types.Schema(type="OBJECT", properties={"islem": types.Schema(type="STRING", description="kapat, yeniden_baslat veya iptal")}, required=["islem"])
        ),
        types.FunctionDeclaration(
            name="uyku_zamanlayici",
            description="Belirtilen dakika sonra bilgisayarı kapatır.",
            parameters=types.Schema(type="OBJECT", properties={"dakika": types.Schema(type="INTEGER", description="Kaç dakika sonra kapansın")}, required=["dakika"])
        ),
        types.FunctionDeclaration(
            name="sistem_durumu",
            description="CPU, RAM, disk ve batarya durumunu gösterir.",
            parameters=types.Schema(type="OBJECT", properties={})
        ),
        types.FunctionDeclaration(
            name="hava_durumu",
            description="Belirtilen şehrin hava durumunu gösterir.",
            parameters=types.Schema(type="OBJECT", properties={"sehir": types.Schema(type="STRING", description="Şehir adı")}, required=["sehir"])
        ),
        types.FunctionDeclaration(
            name="not_ekle",
            description="Bir not kaydeder, hatırlatmak istediğin şeyleri saklar.",
            parameters=types.Schema(type="OBJECT", properties={"not": types.Schema(type="STRING")}, required=["not"])
        ),
        types.FunctionDeclaration(
            name="notlari_goster",
            description="Kaydedilen notları gösterir.",
            parameters=types.Schema(type="OBJECT", properties={})
        ),
        types.FunctionDeclaration(
            name="not_sil",
            description="Tüm notları siler.",
            parameters=types.Schema(type="OBJECT", properties={})
        ),
        types.FunctionDeclaration(
            name="kamera_mod",
            description="Kamera modunu açar veya kapatır. Açıkken el hareketleriyle müzik kontrolü yapılabilir.",
            parameters=types.Schema(type="OBJECT", properties={"islem": types.Schema(type="STRING", description="ac veya kapat")}, required=["islem"])
        ),
        types.FunctionDeclaration(
            name="klasor_ac",
            description="Klasör açar: masaustu, belgeler, indirilenler, resimler, muzik",
            parameters=types.Schema(type="OBJECT", properties={"klasor": types.Schema(type="STRING")}, required=["klasor"])
        ),
        types.FunctionDeclaration(
            name="ekran_goruntusu",
            description="Ekran görüntüsü alır.",
            parameters=types.Schema(type="OBJECT", properties={})
        ),
    ])
]

async def main():
    p = pyaudio.PyAudio()
    mikrofon = p.open(format=FORMAT, channels=CHANNELS, rate=SEND_SAMPLE_RATE, input=True, frames_per_buffer=CHUNK)
    hoparlor = p.open(format=FORMAT, channels=CHANNELS, rate=RECEIVE_SAMPLE_RATE, output=True, frames_per_buffer=CHUNK)

    print("🤖 Jarvis başlatılıyor...")

    client = genai.Client(api_key=GEMINI_API_KEY, http_options={"api_version": "v1beta"})

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")
            )
        ),
        system_instruction=types.Content(parts=[types.Part(text="""Sen Jarvis'sin. Tony Stark'ın yapay zeka asistanı.
Zeki, alaycı ama sadık. Türkçe veya İngilizce konuşulursa anlarsın ama HER ZAMAN Türkçe cevap verirsin.
Kısa ve net konuş. Markdown kullanma.

Yeteneklerin:
- Uygulama açma: uygulama_ac
- Web/YouTube arama: web_ara
- Ekranda tıklama/yazma: ekranda_bul_tikla, ekranda_bul_yaz
- Ses kontrolü: ses_kontrol
- Sistem durumu: sistem_durumu (CPU, RAM, disk, batarya)
- Hava durumu: hava_durumu
- Not alma: not_ekle, notlari_goster, not_sil
- Zamanlayıcı: uyku_zamanlayici
- Kamera modu (el hareketleri): kamera_mod
- Bilgisayar kapatma: bilgisayar_kapat

SADECE kullanıcı istediğinde araçları kullan.""")]),
        tools=TOOLS,
    )

    async with client.aio.live.connect(model="gemini-2.5-flash-native-audio-latest", config=config) as session:
        print("✅ Jarvis hazır! Konuşabilirsiniz...\n")

        async def mikrofon_gonder():
            while True:
                try:
                    veri = await asyncio.get_event_loop().run_in_executor(None, mikrofon.read, CHUNK, False)
                    await session.send_realtime_input(audio=types.Blob(data=veri, mime_type="audio/pcm;rate=16000"))
                except Exception:
                    await asyncio.sleep(0.01)

        async def cevap_al():
            while True:
                try:
                    async for response in session.receive():
                        try:
                            if response.data:
                                hoparlor.write(response.data)
                            if response.tool_call:
                                for fc in response.tool_call.function_calls:
                                    sonuc = tool_calistir(fc.name, dict(fc.args))
                                    await session.send_tool_response(
                                        function_responses=[types.FunctionResponse(
                                            id=fc.id,
                                            name=fc.name,
                                            response={"result": sonuc}
                                        )]
                                    )
                            if response.text:
                                print(f"Jarvis: {response.text}", end="", flush=True)
                        except Exception as e:
                            print(f"⚠️ İç hata: {e}")
                            continue
                except Exception as e:
                    if "1000" in str(e):
                        break
                    print(f"⚠️ Hata: {e}")
                    await asyncio.sleep(0.1)

        await asyncio.gather(mikrofon_gonder(), cevap_al())

if __name__ == "__main__":
    # psutil yüklü mü kontrol et
    try:
        import psutil
    except ImportError:
        print("psutil kuruluyor...")
        subprocess.run("py -3.11 -m pip install psutil", shell=True)

    while True:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\n\nGörüşürüz efendim.")
            kamera_aktif = False
            break
        except Exception as e:
            print(f"Yeniden bağlanıyor... ({e})")