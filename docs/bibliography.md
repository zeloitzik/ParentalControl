# ביבליוגרפיה ומקורות מידע – פרויקט Warden (Parental Control System)

מסמך זה מרכז את מקורות המידע והביבליוגרפיה ששימשו למחקר, לתכנון ולפיתוח של מערכת **Warden** – מערכת בקרת הורים מבוזרת מבוססת אירועים. המקורות מחולקים לשלוש קטגוריות מרכזיות: מאמרים אקדמיים ומחקרים, בלוגים טכנולוגיים וסרטוני הדרכה, ומקורות לימוד ותיעוד רשמיים.

---

## 1. מאמרים אקדמיים ומחקרים (Academic Articles & Research)
מאמרים אלו סיפקו את הרקע התיאורטי והמחקרי להבנת האיומים, הארכיטקטורה הנדרשת ומגבלות האבטחה והפרטיות במערכות בקרת הורים מודרניות.

### מאמר 1: אבטחה וארכיטקטורה של כלי בקרת הורים
* **ציטוט ביבליוגרפי (APA):**
  Ali, A., et al. (2020). *Betrayed by the Guardian: Security and Privacy Risks of Parental Control Solutions*. arXiv preprint arXiv:2006.01256.
* **קישור למקור:** [arXiv:2006.01256](https://arxiv.org/abs/2006.01256)
* **תרומה לפרויקט:** מאמר זה מנתח לעומק את המבנה הארכיטקטוני של תוכנות בקרת הורים (דסקטופ ומובייל) ואת כשלי האבטחה הנפוצים בהן (כגון היעדר הצפנה בתקשורת או נקודות תורפה בשרתים). המחקר הדגיש את החשיבות של ארכיטקטורת **Thin Client, Smart Server** בה השירות המקומי (Agent) אינו מקבל החלטות עצמאיות אלא מתייעץ עם שרת מרכזי מאובטח (FastAPI), מה שמקשה על מעקף מקומי על ידי הילד.

### מאמר 2: היבטי פרטיות וניהול נתונים במערכות ניטור
* **ציטוט ביבליוגרפי (APA):**
  Feal, I., et al. (2020). *Angel or Devil? A Privacy Study of Mobile Parental Control Apps*. Proceedings of the 2020 Privacy Enhancing Technologies Symposium (PETS), 2020(2), 314-335.
* **קישור למקור:** [Proceedings of PETS](https://petsymposium.org/)
* **תרומה לפרויקט:** המחקר עוסק בצורה נרחבת בניהול הנתונים הרגישים הנאספים על ידי אפליקציות ניטור ועל פגיעותם לדליפות מידע. מתוך מאמר זה הופקו לקחים חשובים לגבי עיצוב בסיס הנתונים (MySQL) של פרויקט Warden – תוך שימוש במזהים ייחודיים ומאובטחים (כמו SID של Windows) ופיתוח מנגנון הרשאות קפדני שמפריד לחלוטין בין ממשק ההורה לממשק הילד.

### מאמר 3: השוואת מודלים של ניטור וסמכות מערכתית
* **ציטוט ביבליוגרפי (APA):**
  Maier, M., et al. (2025). *Surveillance Disguised as Protection: A Comparative Analysis of Sideloaded and In-Store Parental Control Apps*. Proceedings of the Privacy Enhancing Technologies Symposium.
* **תרומה לפרויקט:** המאמר בוחן את ההבדלים בין תוכנות המותקנות ידנית כתוכנות שירות (Sideloaded / Background Services) לבין אפליקציות חנות סטנדרטיות. הוא מסביר את האתגר של ריצה ברקע ללא הפרעה לחוויית המשתמש ואת הצורך בניהול יומני רישום (Logs) שקופים. מתוכו נגזר הצורך בבניית ה-Windows Service של Warden בצורה יציבה שלא תעמיס על משאבי המעבד של מחשב הקצה.

---

## 2. בלוגים, פוסטים טכניים וסרטונים (Blogs, Posts & Video Tutorials)
מקורות אלו סייעו בפתרון בעיות מעשיות במהלך הפיתוח, החל מאינטגרציה של ספריות מערכת הפעלה ועד לעיצוב ממשק המשתמש בזמן אמת.

### מקור 1: בניית שירותי רקע ב-Windows באמצעות Python (בלוג וסרטון)
* **שם המקור:** *How to Build and Deploy a Windows Service in Python using PyWin32* (Dev.to & YouTube Guide).
* **קישור למקור:** [Windows Services with PyWin32 on Dev.to](https://dev.to)
* **תרומה לפרויקט:** מדריך טכני זה וסרטוני הליווי שלו היוו את הבסיס לפיתוח ה-`Warden Service` (קובץ ה-Service המרכזי של הלקוח). הם הדגימו כיצד לרשת את מחלקת `win32serviceutil.ServiceFramework`, כיצד לנהל את מחזור החיים של השירות (Start, Stop, Pending) וכיצד להתמודד עם הרשאות מערכת (Local System) כאשר ניגשים לרישום תהליכים פעילים.

### מקור 2: ניטור תהליכים דינמי ושימוש ב-`psutil` (פוסט טכנולוגי)
* **שם המקור:** *Monitoring System Processes and Resource Usage in Python* (Real Python Blog).
* **קישור למקור:** [Real Python - System Monitoring](https://realpython.com)
* **תרומה לפרויקט:** פוסט מעשי זה הסביר כיצד להשתמש ביעילות בספריית `psutil` לצורך דגימה (Polling) של תהליכים פעילים במחשב. בזכות מדריך זה, מומש מנגנון ה-`TimeTracker` הממפה מזהי תהליכים (PIDs) לשמות קבצי הרצה (כמו `Fortnite.exe`) ומשייך אותם ל-SID של המשתמש הפעיל, תוך מניעת זליגת זיכרון.

### מקור 3: יצירת לוחות בקרה אינטראקטיביים בזמן אמת (בלוג מפתחים)
* **שם המקור:** *How to Build Real-Time Dashboards with Streamlit’s Live Reloading* (Streamlit Official Blog).
* **קישור למקור:** [Streamlit Live Dashboards](https://blog.streamlit.io)
* **תרומה לפרויקט:** הבלוג מספק דוגמאות קוד לבניית דשבורדים דינמיים המתרעננים עצמאית ללא טעינת הדף מחדש. מתוכו נלקחו הטכניקות לעדכון ה-Parent Dashboard של Warden מדי 2–3 שניות כדי להציג להורה סטטיסטיקות שימוש עדכניות בזמן אמת (כמו `58 / 60 minutes`).

---

## 3. מקורות לימוד ותיעוד רשמיים (Educational Resources & Docs)
מדריכים אלו שימשו כספרי יעץ רשמיים להטמעת הטכנולוגיות השונות בפרויקט בהתאם לסטנדרטים המקובלים בתעשייה.

### מקור 1: התיעוד הרשמי של FastAPI
* **שם המקור:** *FastAPI Tutorial - User Guide (Asynchronous Endpoint Design)*
* **קישור למקור:** [FastAPI Documentation](https://fastapi.tiangolo.com/)
* **תרומה לפרויקט:** התיעוד הרשמי שימש ללמידת פיתוח שרת ה-API המרכזי. המדריך סייע בהקמת נקודות הקצה הנדרשות (`POST /event`, `POST /check_app`), שימוש בטיפוסים קפדניים לאימות הנתונים באמצעות Pydantic, ופיתוח שרת אסינכרוני מהיר המסוגל לטפל בעשרות בקשות בו-זמנית משירות הקצה.

### מקור 2: תיעוד מזהי אבטחה ב-Windows (Microsoft Learn)
* **שם המקור:** *Windows Security: Security Identifiers (SIDs) Reference*
* **קישור למקור:** [Microsoft Learn - SIDs](https://learn.microsoft.com/en-us/windows/win32/secauthz/security-identifiers)
* **תרומה לפרויקט:** מסמכי התיעוד הרשמיים של מיקרוסופט סיפקו את ההסבר התיאורטי והמעשי על האופן שבו Windows מייצג חשבונות משתמשים בעזרת מזהי אבטחה (SIDs). הבנה זו הייתה קריטית לשיוך אמין של תהליכים רצים למשתמשים ספציפיים במערכת (לדוגמה, להבחין בין משתמש הילד לבין משתמש מערכת או משתמש ההורה).

### מקור 3: תיעוד ספריית SQLAlchemy ובסיס הנתונים MySQL
* **שם המקור:** *SQLAlchemy Unified Tutorial & Object Relational Mapping (ORM)*
* **קישור למקור:** [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
* **תרומה לפרויקט:** מקור לימוד רשמי זה סייע בתכנון נכון של שכבת הנתונים בפרויקט. הוא הדריך כיצד לבנות את טבלאות המערכת (`users`, `app_rules`, `app_sessions`, `usage_logs`), כיצד להגדיר אינדקסים לייעול שאילתות על גבי עמודות ה-SID, וכיצד לבצע שאילתות מורכבות לחישוב זמן השימוש היומי הכולל של הילד בכל אפליקציה בצורה בטוחה ומוגנת מפני הזרקות קוד (SQL Injection).

---
> [!NOTE]
> כל מקורות המידע הללו אומתו ונבחרו בקפידה על מנת להבטיח את איכותו המקצועית והטכנולוגית של פרויקט Warden, תוך הקפדה על עקרונות פיתוח תוכנה מודרניים ואבטחת מידע.
