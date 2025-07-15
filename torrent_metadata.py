import re
import bencodepy
from sqlalchemy.orm import Session

from models import Torrent, TorrentFile

def strip_bbcode(text):
    text = re.sub(r'\[(img|thumb)(=[^\]]+)?\].*?\[/\1\]', '', text, flags=re.IGNORECASE | re.DOTALL)

    text = re.sub(r'\[/?[^\[\]=\]]+(=[^\]]+)?\]', '', text)

    text = re.sub(r'\n\s*\n+', '\n\n', text)

    return text.strip()

def scan_torrent_files(db: Session, directory):
    import os

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.torrent'):
                torrent_file = os.path.join(root, file)
                parse_torrent(db, torrent_file)

def parse_torrent(db: Session, torrent_file):
    with open(torrent_file, 'rb') as f:
        torrent = bencodepy.decode(f.read())

    metadata = torrent.get(b'metadata')
    info = torrent.get(b'info')
    name = str(info.get(b'name'), 'utf-8', errors='ignore')

    if db.query(Torrent).filter(Torrent.name == name).first():
        print(f"Torrent '{name}' already exists in the database.")
        return

    taglist = metadata.get(b'taglist')
    taglist = [str(tag, 'utf-8', errors='ignore') for tag in taglist] if taglist else []

    description = str(metadata.get(b'description'), 'utf-8', errors='ignore')
    description = strip_bbcode(description)

    files = []
    if b'files' in info:  # multi-file
        for file_entry in info[b'files']:
            subpath = "/".join(x.decode('utf-8', errors='ignore') for x in file_entry[b'path'])
            fullpath = f"{name}/{subpath}"
            size = int(file_entry.get(b'length', 0))
            files.append(TorrentFile(path=fullpath,size=size))
    else:  # single-file
        fullpath = name
        size = int(info.get(b'length', 0))
        files.append(TorrentFile(path=fullpath,size=size))

    torrent_obj = Torrent(
        name=name,
        description=description,
        taglist=taglist,
        files=files
    )

    db.add(torrent_obj)
    db.commit()

    # print(name)
    # print("---")
    # print(description)
    # print("---")
    # print(taglist)
    # print("---")
    # print(files)