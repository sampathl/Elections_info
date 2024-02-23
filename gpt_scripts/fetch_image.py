import requests
import shutil

def fetch_image(keyword, output_file):
    client_id = "YOUR_UNSPLASH_ACCESS_KEY"  # Replace with your Unsplash access key
    url = f"https://api.unsplash.com/search/photos?page=1&query={keyword}&client_id={client_id}"
    response = requests.get(url)
    data = response.json()

    if data["results"]:
        image_url = data["results"][0]["urls"]["regular"]
        res = requests.get(image_url, stream=True)

        if res.status_code == 200:
            with open(output_file, 'wb') as f:
                shutil.copyfileobj(res.raw, f)
            print(f"Image successfully downloaded: {output_file}")
        else:
            print("Failed to download image")
    else:
        print("No results found")

# Example usage
fetch_image("nature", "nature.jpg")
