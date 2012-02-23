#!/usr/bin/env python
import os


HTDIR = '/var/cache/www/'

def check():
    for root, dirs, files in os.walk(HTDIR):
        for f in files:
            fpath = os.path.join(root, f)
            if 'viking' not in fpath:
                continue
            for key in ('flv', 'mp4', 'html'):
                if key in fpath:
                    print key, fpath

def main():
    check()

if __name__ == '__main__':
	main()
