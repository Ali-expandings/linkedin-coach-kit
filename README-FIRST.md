# LinkedIn Coach — start here

An AI coach that reads your LinkedIn, asks you only what it can't find, writes a professional
profile, and fills it in for you. You approve everything once before it goes live.

**You need:** a Windows 10 or 11 laptop, the OpenCode app connected to Anthropic (Claude Opus 5.5),
Google Chrome, and internet.

## 1. Set up (once, about 10 minutes)

1. Get the kit: on https://github.com/Ali-expandings/linkedin-coach-kit click the green
   **Code** button → **Download ZIP** (or use the zip someone sent you).
   Unzip it somewhere simple, for example `C:\linkedin-coach`: right-click the zip →
   **Extract All**. Don't run anything from inside the zip.
2. Double-click **`setup.cmd`**.
   If Windows shows "Windows protected your PC", click **More info → Run anyway**.
3. Wait. When a browser window opens, **sign in to LinkedIn** in it. It closes by itself.
4. When you see **Setup finished**, press any key to close the window.

## 2. Use it

1. Open the **OpenCode** app.
2. Open the `linkedin-coach` folder as a project.
3. Type **hi** and press Enter. The coach asks which language you want and takes it from there.

A Chrome window opens while the coach works; that's how it edits your profile. It shows a grey bar
saying "unsupported command-line flag". That's expected and safe. Leave the window open and don't
click in it while the coach is typing.

Optional: before you start, put any of these into the `inbox` folder — your CV, certificates, a
profile photo, or an old chat with ChatGPT about your CV (copy the chat into a `.txt` file).

## Optional: edit through an API instead of the browser

With a **Unipile** API key the coach changes most of your profile with direct API calls: About,
headline, experience, education, skills, open to work and photo. The browser is then only needed
for certifications, projects and languages (or the coach gives you that text to paste yourself).
Unipile is a paid service (about $55/month) with a **7-day free trial, no card needed**, which is
enough for one profile makeover.

1. Sign up at https://dashboard.unipile.com/signup
2. Create an API key in the dashboard and copy it (it's shown only once).
3. Run `setup.cmd` again and paste the key when it asks. The first time the coach runs, it sends you
   a link to connect your LinkedIn to Unipile.

Unipile is a separate company, not LinkedIn. Connecting adds a session you can see (and end) in
LinkedIn under Settings → Sign in & security → Where you're signed in. Once the key is in the folder,
don't share the folder with anyone.

## If something goes wrong

- Run `setup.cmd` again. It's safe and fixes most problems.
- Don't move the folder after setup. If you do, run `setup.cmd` again.
- Still stuck: take a screenshot and send it to whoever gave you this kit.

---

# المدرب الخاص بـ LinkedIn — ابدأ من هنا

مدرب ذكاء اصطناعي يقرأ حسابك على LinkedIn، ويسألك فقط عن المعلومات اللي مش موجودة، ويكتب لك
بروفايل احترافي، ويعدّله بنفسه. هتوافق على كل التعديلات مرة واحدة قبل ما تتنشر.

**محتاج:** لابتوب ويندوز 10 أو 11، وبرنامج OpenCode متوصّل بـ Anthropic (Claude Opus 5.5)،
وجوجل كروم، وإنترنت.

## 1. التسطيب (مرة واحدة، حوالي 10 دقايق)

1. نزّل الكيت: من https://github.com/Ali-expandings/linkedin-coach-kit دوس الزرار الأخضر
   **Code** ← **Download ZIP** (أو استخدم الملف المضغوط اللي اتبعتلك).
   فك الضغط في مكان بسيط، مثلاً `C:\linkedin-coach`: كليك يمين على الملف المضغوط ←
   **Extract All**. ما تشغلش أي حاجة من جوه الملف المضغوط.
2. دبل كليك على **`setup.cmd`**.
   لو ويندوز ظهرت رسالة "Windows protected your PC" دوس **More info ← Run anyway**.
3. استنى. لما يفتح متصفح، **سجّل دخول على LinkedIn** فيه، وهيقفل لوحده.
4. لما تشوف **Setup finished** دوس أي زرار عشان تقفل الشاشة.

## 2. الاستخدام

1. افتح برنامج **OpenCode**.
2. افتح فولدر `linkedin-coach` كمشروع (project).
3. اكتب **hi** ودوس Enter. المدرب هيسألك تحب تتكلم بأي لغة ويكمّل هو.

هيفتح شباك كروم والمدرب شغال، ده اللي بيعدّل بيه البروفايل. هيظهر فيه شريط رمادي مكتوب فيه
"unsupported command-line flag"، ده طبيعي ومفيش مشكلة. سيب الشباك مفتوح وما تدوسش جواه والمدرب بيكتب.

اختياري: قبل ما تبدأ حط في فولدر `inbox` أي حاجة من دول: الـ CV، الشهادات، صورة البروفايل، أو
محادثة قديمة مع ChatGPT عن الـ CV (انسخها في ملف `.txt`).

## اختياري: التعديل عن طريق API بدل المتصفح

لو عندك مفتاح API من **Unipile**، المدرب هيعدّل أغلب البروفايل باستدعاءات API مباشرة: النبذة (About)،
العنوان (Headline)، الخبرات، التعليم، المهارات، Open to work والصورة. المتصفح هيتستخدم بس للشهادات
والمشاريع واللغات (أو المدرب يديك النص تلزقه بنفسك). Unipile خدمة مدفوعة (حوالي 55 دولار في الشهر)
وفيها **تجربة مجانية 7 أيام من غير كارت**، وده كفاية لتظبيط بروفايل مرة واحدة.

1. اعمل حساب من https://dashboard.unipile.com/signup
2. اعمل API key من الداشبورد وانسخه (بيظهر مرة واحدة بس).
3. شغّل `setup.cmd` تاني والزق المفتاح لما يطلبه. أول مرة المدرب يشتغل هيبعتلك لينك توصّل بيه
   LinkedIn بتاعك بـ Unipile.

Unipile شركة منفصلة مش LinkedIn. التوصيل بيضيف جلسة تقدر تشوفها (وتقفلها) من إعدادات LinkedIn في
Sign in & security ← Where you're signed in. بعد ما تحط المفتاح ما تبعتش الفولدر لحد.

## لو حصلت مشكلة

- شغّل `setup.cmd` تاني، آمن وبيحل أغلب المشاكل.
- ما تنقلش الفولدر بعد التسطيب. لو نقلته شغّل `setup.cmd` تاني.
- لسه فيه مشكلة؟ صوّر الشاشة وابعتها للي بعتلك الكيت ده.
