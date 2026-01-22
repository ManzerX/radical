import os, datetime
p = r'd:/Lars/HBO/DOSI/Radical github/radical/aqcuisition_fase-scrapers/Youtube/output/video_data.json'
print('exists', os.path.exists(p))
print('mtime', datetime.datetime.fromtimestamp(os.path.getmtime(p)) if os.path.exists(p) else 'no file')
print('main mtime', datetime.datetime.fromtimestamp(os.path.getmtime(r'd:/Lars/HBO/DOSI/Radical github/radical/aqcuisition_fase-scrapers/Youtube/main.py')))
print('cwd', os.getcwd())
