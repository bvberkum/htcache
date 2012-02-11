import os


HTDIR = os.path.expanduser('~/project/htcache/htdir')

def get_playing_now():
    for root, dirs, files in os.walk(HTDIR):
        if root == HTDIR:
            for d in list(dirs):
                if 'last.fm' not in d and 'audioscrobbler' not in d:
                    dirs.remove(d)
        for f in files:
            if f.endswith('.mp3'):
                fpath = os.path.join(root, f)
                print fpath

def main():
    #jwhile True:
    now_playing = get_playing_now()


if __name__ == '__main__':
    main()
