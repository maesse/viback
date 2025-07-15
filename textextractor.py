import json
from openai import BaseModel, OpenAI
import os
from config import get_media_folders

class Tags(BaseModel):
    tags: list[str] | None
    actors: list[str] | None
    series: str | None
    scene_name: str | None

def extract_tags_from_path(path: str) -> Tags:
    """Extract tags from a video file path."""

    name, _ = os.path.splitext(os.path.normpath(path))
    prompt = """Look if there is any actor names, scene names or series name in the following filename. Ignore metadata, codes and identifiers: """ + name

    client = OpenAI(base_url="http://127.0.0.1:8080/v1", api_key="hi")
    
    response = client.chat.completions.parse(
        model="mistral-7b-instruct-v0.2.Q4_K_M",
        messages=[
            {"role": "system", "content": "You are an extractor that outputs tags. Only include tags with high confidence."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        temperature=0,
        max_tokens=512,
        response_format=Tags,
    )
    content = response.choices[0].message.content.strip()

    # Try to parse the response as JSON and validate it with the Tags model
    try:
        data = json.loads(content)
        return Tags(**data)
    except Exception as e:
        print("⚠️ Failed to parse response:")
        print(content)
        raise e

def test(path: str):
    tags = extract_tags_from_path(path)
    print(tags)
