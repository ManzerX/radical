import traceback
try:
    import comment_scraper
    print('Imported', comment_scraper)
    print([name for name in dir(comment_scraper) if not name.startswith('__')])
except Exception:
    traceback.print_exc()
print('cwd:', __import__('os').getcwd())
print('file:', comment_scraper.__file__ if 'comment_scraper' in globals() else 'not imported')
