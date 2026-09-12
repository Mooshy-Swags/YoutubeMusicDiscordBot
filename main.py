import os
import shutil

import music

if os.path.isdir(music.MUSIC_CACHE):
    shutil.rmtree(music.MUSIC_CACHE)
    os.makedirs(music.MUSIC_CACHE)

import bot