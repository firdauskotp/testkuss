Task distribution

1. Firdaus - backend + setup meeting
2. Ahmed - backup backend (if free after Josephine's project)
3. Nasran - frontend (focusing on Josephine's project first for now)
4. Arif - backup frontend (if free after Josephine's project)
5. Asyraf - backup frontend / business analyst
6. Syakur - QA / backup frontend
7. Khid - QA

## Running the App

Change directory to the backend folder

```
cd backend
```

Install the required libraries:
```
pip3 install -r requirements.txt
```
Start the Flask app:
```
python app.py
```

If Mac:

```
python3 app.py
```

Open `http://127.0.0.1:5000/` in your browser.

## Rules for developing / committing

Clone the project first:

```
git clone "https://gitlab.com/mididle/kuss-essentials.git"
```

Open the cloned folder on your IDE

Fetch the available branches

```
git fetch
```

Change to your branch (if exists)

```
git checkout branch_name
```

If branch doesn't exist

```
git checkout -b branch_name
```

Always pull from main first

```
git pull origin main
```

Once done with your coding, add, commit, pull and push your files

```
git add .
git commit -m "your commit message, please put something that shows what fixes you made or things added"
git pull origin main
git push
```

Please note that before you push, you might need to change pull conflicts if occured
For the first push to your branch, you will need to use:

```
git push --set-upstream origin branch_name
```