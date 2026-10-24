# SECURE EXAM PAPER CLOUD

## Brief description
Secure Exam Paper Cloud is a Cloud Computing micro project that demonstrates how examination question papers can be encrypted, stored, and released only at a scheduled time. It includes role-based access, a demo second authentication factor (OTP), a secure viewer, and audit logs.

This is an educational prototype, not a production examination platform. It demonstrates the architecture in the supplied diagram using a local Flask web app and SQLite database. To make it a real cloud deployment, deploy the app to a cloud VM/platform and use managed storage, HTTPS, a secret manager, and a real MFA provider.

## Technologies/tools used
- Python 3
- Flask (web application)
- SQLite (metadata, encrypted paper data, audit logs)
- Fernet symmetric encryption from `cryptography`
- HTML, CSS, Jinja templates
- Git and GitHub

## Features mapped to the architecture
1. **Question paper creation:** authorized examiner/admin uploads a file.
2. **Encryption module:** uploaded bytes are encrypted before database storage.
3. **Secure storage:** encrypted content is stored in SQLite.
4. **Authorized access:** role checks restrict upload and audit-log pages.
5. **Timed release:** the server refuses to decrypt a paper before its scheduled release time.
6. **Secure viewer:** released text files are rendered in a view-only page without a download button.
7. **Exam centre:** a student account can access released papers from the portal.
8. **Monitoring and logging:** login and paper-access events are recorded.
9. **Audit and reports:** administrator can inspect audit logs.

## Requirements
- Python 3.10 or newer
- pip
- A terminal / command prompt
- Internet connection for first-time dependency installation

## Installation and run
1. Download or clone this repository.
2. Open a terminal in the project directory.
3. Create a virtual environment:

   **Windows**
   ```bash
   py -m venv .venv
   .venv\\Scripts\\activate
   ```

   **macOS/Linux**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Start the app:
   ```bash
   python app.py
   ```
6. Open `http://127.0.0.1:5000` in your browser.

The database and encryption key are generated automatically on first run. Keep `secret.key` private; losing it means existing encrypted papers cannot be decrypted.

## Demo accounts
| Role | Username | Password | Demo OTP |
|---|---|---|---|
| Administrator | `admin` | `Admin@123` | `123456` |
| Examiner | `examiner` | `Exam@123` | `234567` |
| Student | `student` | `Student@123` | `345678` |

These credentials and fixed OTP values are for local demonstration only. Change/remove them before any deployment.

## How to test
1. Sign in as `examiner` and enter OTP `234567`.
2. Select **Add question paper**.
3. Enter a title, choose a release time a few minutes in the future, and upload a `.txt` file.
4. Return to the dashboard. Opening the paper before its release time should show **Paper is still locked**.
5. After the scheduled time, open it again to view the text.
6. Sign in as `admin` to view audit logs at **View all logs**.
7. Try signing in as `student`; the student can view released papers but cannot upload or view administrator logs.

## Sample input and output
**Sample input file** (`sample_question_paper.txt`):
```text
CLOUD COMPUTING - SAMPLE TEST
1. Define cloud computing.
2. Explain IaaS, PaaS and SaaS.
3. State two benefits of cloud storage.
```

**Expected output**
- After upload: `Question paper encrypted and uploaded to the database.`
- Before release: `Paper is still locked.`
- After release: the paper content appears in the secure viewer.
- In the admin audit page: events such as `PAPER_ENCRYPTED_UPLOADED`, `RELEASE_BLOCKED`, and `PAPER_VIEWED`.

## Project structure
```text
secure_exam_cloud/
├── app.py
├── requirements.txt
├── README.md
├── sample_question_paper.txt
├── .gitignore
├── templates/
│   ├── base.html
│   ├── home.html
│   ├── login.html
│   ├── otp.html
│   ├── dashboard.html
│   ├── upload.html
│   ├── locked.html
│   ├── viewer.html
│   ├── logs.html
│   └── error.html
└── static/
    └── style.css
```

## Module purpose
- `app.py`: routes, login/MFA demo, role checks, encryption, timed release, SQLite access, and audit logging.
- `templates/`: web pages for the portal, upload form, dashboard, locked screen, viewer, and audit report.
- `static/style.css`: responsive dark user interface.
- `requirements.txt`: Python dependencies.
- `sample_question_paper.txt`: sample file to upload.
- `.gitignore`: excludes database, secret key, and Python environment files from Git.

## Security notes / limitations
- The demo uses a fixed OTP stored in the local database; this is not real MFA.
- A normal website cannot reliably prevent screenshots, browser developer tools, or external photography. The secure viewer only omits a download button and logs access.
- The app runs locally by default; it is not automatically deployed to a cloud provider.
- For real deployment, use HTTPS, cloud object storage, a managed database, secure secret storage, real MFA, production server settings, and carefully designed authorization.
- Do not upload real or confidential examination papers to this classroom demo.
