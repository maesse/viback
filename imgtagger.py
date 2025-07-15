from openai import OpenAI
import base64
import os

from config import get_config


def generate_tags(path: str): 
    """Generate tags for a video using an AI model."""
    if not os.path.exists(path):
        print(f"File not found: {path}")
        raise FileNotFoundError(f"File not found: {path}")
    
    with open(path, "rb") as f:
        image_bytes = f.read()
    img_base64 = base64.b64encode(image_bytes).decode('utf-8')

    cfg = get_config()
    prompt = cfg['IMAGE_TAGGER']['prompt']
    client = OpenAI(base_url="http://127.0.0.1:8080/v1", api_key="hi")
    print(f"Generating tags for {path}...")
    response = client.chat.completions.create(
        model="JoyCapture",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_base64}"
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        temperature=0,
        max_tokens=512,
    )
    print("Tags response received.")
    taglist = response.choices[0].message.content
    tags = [tag.strip() for tag in taglist.split(',') if tag.strip()]
    return {
        "tags": tags,
        "raw": taglist.strip(),
        "prompt": prompt,
    }
    # print(taglist.replace(',', '\n'))