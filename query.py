import os
from typing import Dict, List, TypedDict
from pyparsing import (
    MatchFirst, QuotedString, Word, dblQuotedString, Regex, oneOf, Suppress,
    Group, OneOrMore, removeQuotes, ParseResults
)
from sqlalchemy import func, literal_column, or_
from sqlalchemy.orm import Session
from models import Torrent, TorrentFile, Video, VideoTagSet
from vector_index import search_similar_from_string, search_similar_from_tags

class ParsedQuery(TypedDict):
    terms: List[str]
    filters: Dict[str, List[str]]

def build_query_parser():
    filter_keys = oneOf("tag path vision")
    quoted = MatchFirst([
        QuotedString('"', unquoteResults=True, multiline=True, endQuoteChar='"'),
        QuotedString("'", unquoteResults=True, multiline=True, endQuoteChar="'"),
    ])
    unquoted = Regex(r"[^\s\"']+")
    value = quoted | unquoted
    filter_expr = Group(filter_keys("key") + Suppress(":") + value("value"))
    text_term = MatchFirst([
        quoted,
        Regex(r"(?!\b(?:tag|path|vision):)[^\s\"']+"),
    ]).setParseAction(lambda t: t[0])
    return OneOrMore(filter_expr("filters*") | text_term("terms*"))

def parse_query_string(query: str) -> ParsedQuery:
    if not query:
        return ParsedQuery(terms=[], filters={})
    parser = build_query_parser()
    res = parser.parseString(query)
    terms = res.get("terms", [])
    filters: Dict[str, List[str]] = {}
    for f in res.get("filters", []):
        filters.setdefault(f["key"], []).append(f["value"])
    return ParsedQuery(terms=terms, filters=filters)

def search_query(db: Session, terms: List[str] = None, tags: List[str] = None, path: List[str] = None, vision: List[str] = None, limit: int = 20, rerank: bool = True) -> List[Video]:
    use_vector = len(terms) > 0
    if use_vector:
        text = ' '.join(terms)
        texts = text.split(',')
        texts = [t.strip() for t in texts]
        vector_results = search_similar_from_string(db, texts, k = limit, rerank_enabled=rerank)
        video_id_ordered = [video.id for video in vector_results]
        id_to_index = {vid: i for i, vid in enumerate(video_id_ordered)}
        query = db.query(Video).filter(Video.id.in_(video_id_ordered))
    else:
        query = db.query(Video)

    if tags:
        tag_count = len(tags)

        query = (
            query
            .filter(Video.torrent_tags != None)
            .join(func.json_each(Video.torrent_tags), literal_column("1"))
            .filter(
                literal_column("json_each.value").in_(tags)
            )
            .group_by(Video.id)
            .having(func.count(func.distinct(literal_column("json_each.value"))) == tag_count)
        )
    
    if vision:
        query = (
            query
            .outerjoin(Video.tag_sets)
            .join(
                func.json_each(VideoTagSet.tags),
                literal_column("1")
            )
            .filter(
                literal_column("json_each.value").in_(vision)
            )
        )

    
    if path and len(path) > 0:
        norm_path = os.path.normpath(path[0])
        query = query.filter(Video.searchpath.startswith(norm_path))

    
    videos = query.distinct().all()

    if use_vector:
        videos.sort(key=lambda v: id_to_index.get(v.id, float('inf')))

    return videos
    

if __name__ == "__main__":
    print(parse_query_string('beach tag:"early morning" tag:water path:"New Folder/file.mpg" hello'))