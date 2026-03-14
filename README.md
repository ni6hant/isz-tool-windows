# ISZtoISO – Windows GUI converter (ISZ → ISO)

> ⚙️ **AI‑assisted development**  
> This project was assembled with the help of an AI language model (OpenAI’s ChatGPT).  
> The core algorithm was originally written by [**Olivier Serres**](https://github.com/oserres) and a clean GUI wrapper + packaging was added by [**ni6hant**](https://github.com/ni6hant) for debugging and idea integration.
> 
> [**ni6hant**](https://github.com/ni6hant) would like to point out at this point the deep disgust he feels in using AI to write this code for him knowing it will increase the prices of PC parts so much more that there will be a war. He takes responsibility for the rich vs. poor war that will happen in the future no matter which side he winds up then.

---

## 📦 What is this?

ISZtoISO is a tiny Windows‑x64 **stand‑alone** program that converts a `.isz` (ISO‑packed) file into a normal `.iso` image.  
It runs directly from the GitHub releases – you do **not** need Python or any external libraries installed on the target machine.  

---

## 🚀 For Users:

1. **Download** the *latest release* from the [Releases page](https://github.com/ni6hant/isz-tool-windows/releases/).  
   Find the file named `ISZtoISO.exe` inside the archive and extract it to a folder of your choice.

2. **Run** `ISZtoISO.exe`.  
   A small window will appear with two file fields, a *Browse…* button on each side, a *Convert → ISO* button and a progress bar.

3. **Choose the source file**  
   - Click **Browse…** next to *Source ISZ file* and select the first `.isz` file of your multi‑part set (e.g. `image.isz`).  
   - The program will automatically look for the other parts (`image.part01.isz`, `image.part02a.isz`, …).  
   - If no other parts are needed the conversion will still work.

4. **Choose the destination**  
   - Click **Browse…** next to *Destination ISO* and pick the folder where you want the resulting `.iso` to be written.  
   - The default suggestion is the same name as the source file but with the extension changed to `.iso`.

5. **Convert**  
   - Click **Convert → ISO**.  
   - The progress bar at the bottom will update as blocks are decompressed.  
   - When finished a dialog box will pop up saying **“Converted to: …”**

6. **Done!**  
   The `.iso` is now ready to be mounted, burned to DVD, or used in a virtual machine.

> **Common question**  
> *Why do I get an “Error: Unable to read block” message?*  
> The most frequent cause is a missing part of a multi‑file set. Make sure the whole series is in the same directory with the exact filenames the program expects.  

---

## 🛠️ Building the executable – For developers

If you want to build the `.exe` yourself (for example, after making changes or updating the GUI), follow these steps:

### 1️⃣ Prerequisites

| Item | Version | Why |
|------|---------|-----|
| Python | ≥ 3.10 | Needed to run [PyInstaller](https://www.pyinstaller.org) |
| pip | – | Package installer (comes with Python) |
| Git | – | Optional – to clone the repo |

> NOTE: The project was written and tested on **Windows‑10 x64**.  
> If you run on a different OS, you’ll need to cross‑compile or rebuild on a Windows machine.

### 2️⃣ Get the source

```bash
git clone https://github.com/ni6hant/isz2iso_gui.git
cd isz2iso_gui
```

> If you don’t have git, download the ZIP from the repository and extract it.

### 3️⃣ Create a virtual environment (recommended)

```bash
python -m venv .venv
.\.venv\Scripts\activate   # on cmd.exe, use .venv\Scripts\activate.bat
# or:  source .venv/bin/activate  (on Unix)
```

### 4️⃣ Install build dependencies

```bash
pip install --upgrade pip setuptools wheel
pip install pyinstaller
```

> **Tip:** If you already have PyInstaller installed globally, you still get a clean copy inside the virtualenv.

### 5️⃣ Run PyInstaller

```bash
pyinstaller --clean --onefile --noconsole --name ISZtoISO --icon isztosoft.ico isz2iso_gui.py
```

> - `--clean` – removes old build artifacts.  
> - `--onefile` – bundles everything into a single `.exe`.  
> - `--noconsole` – hides the console window.  
> - `--icon` – optional – use a .ico file to give the executable an icon.  
> - `isz2iso_gui.py` – entry point (the file we provided).

> After a few seconds a **`dist/ISZtoISO.exe`** file will appear.  
> You can copy it anywhere – it contains its own Python interpreter and all dependencies.

### 6️⃣ Create a release

1. Zip the `dist` folder (or just the `ISZtoISO.exe`).  
2. Upload the archive to the *Releases* section of your GitHub repo.  
3. Add a short release note (e.g. “Version 1.2.0 – progress bar added, minor bugfixes”).  

### 🧪 Quick test

```bash
# On a clean Windows machine (no Python)
D:\temp\IszToIso\ISZtoISO.exe   # just run it
```

The program should launch, show the GUI and perform conversions as described above.

---

## 📄 License

This project is licensed under the **GNU General Public License v3.0** (or any later version).  
The original ISZ code (by Olivier Serres) is also licensed GPL‑3.0; see the file LICENSE or the header in the source for details.

---

## 👥 Acknowledgements

- **Olivier Serres** – original ISZ‑to‑ISO algorithm.  
- **ni6hant** – debugging, adding the GUI, packaging, and the overall idea to make this a stand‑alone Windows app.  
- **OpenAI** – the AI model that helped structure the code and documentation.  

---

## 📌 FAQ (quick references)

| Question | Answer |
|----------|--------|
| **Do I need an internet connection to run the exe?** | No, all runtime dependencies are bundled. |
| **Will the exe work on PowerShell?** | Yes, simply double‑click or run from PowerShell – it behaves like any other native Windows program. |
| **Can I use it with a Multi‑Part ISZ set that uses a non‑standard naming scheme?** | Only the three following patterns are supported: `image.i01.isz`, `image.part01.isz`, `image.part001.isz`. |
| **What version of Python is included?** | The executable contains Python 3.10.12 (embedded). |
