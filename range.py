import os
from fastapi import HTTPException, Request, Response, status


default_range = 10*1024*1024 - 1

def _get_range_header(range_header: str, file_size: int) -> tuple[int, int]:
    def _invalid_range():
        return HTTPException(
            status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail=f"Invalid request range (Range:{range_header!r})",
        )

    try:
        h = range_header.replace("bytes=", "").split("-")
        start = int(h[0]) if h[0] != "" else 0
        end = int(h[1]) if h[1] != "" else min(start + default_range, file_size - 1)
    except ValueError:
        raise _invalid_range()

    if start > end or start < 0 or end > file_size - 1:
        raise _invalid_range()
    return start, end


def range_requests_response(
    request: Request, file_path: str, content_type: str
):
    """Returns StreamingResponse using Range Requests of a given file"""

    file_size = os.stat(file_path).st_size
    range_header = request.headers.get("range")

    start = 0
    end = file_size - 1

    if range_header is not None:
        start, end = _get_range_header(range_header, file_size)

    with open(file_path, mode="rb") as video_file:
        video_file.seek(start)
        data = video_file.read(end - start + 1)

        headers = {
            'Content-Range': f'bytes {str(start)}-{str(end)}/{file_size}',
            'Accept-Ranges': 'bytes'
        }
        return Response(data, status_code=206, headers=headers, media_type="video/mp4")