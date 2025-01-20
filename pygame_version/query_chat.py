import os
import json
import base64
from urllib.parse import urlparse
import logging
from openai import AzureOpenAI

endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
key = os.getenv("AZURE_OPENAI_API_KEY")
client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_version="2024-02-01",
    api_key=key
)


def encode_image(image_path):
    try:
        with open(image_path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode('utf-8')
            return encoded
    except Exception as e:
        raise e


def image_path_or_url_to_url(image_path_or_url):
    if not is_url(image_path_or_url):
        try:
            base64_image = encode_image(image_path_or_url)
            return f"data:image/jpeg;base64,{base64_image}"
        except Exception as e:
            raise e
    else:
        return image_path_or_url


def is_url(path):
    try:
        result = urlparse(path)
        return all([result.scheme, result.netloc])
    except ValueError as e:
        return False


def query_chat(prompt: str, media_url=None):
    messages = [{"role": "user", "content": prompt}]
    if media_url is not None:
        messages.append({"role": "user", "content": [
            {
                "type": "image_url",
                "image_url": {"url": image_path_or_url_to_url(media_url)}
            },
        ]})

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=300,
        temperature=0.,
    )

    response = completion.choices[0].message.content.strip()
    return response
