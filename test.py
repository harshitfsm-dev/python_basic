import time
import httpx
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

class AsyncTimePass:
    def __init__(self, second: float):
        self.second = second
        self.start_time = 0.0

    async def __aenter__(self):
        self.start_time = time.perf_counter()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        end_time = time.perf_counter()
        elapsed_time = end_time - self.start_time
        remaining = self.second - elapsed_time

        if remaining > 0:
            print(f"⏱️ Work finished in {elapsed_time:.4f}s. Padding block with a {remaining:.4f}s sleep...")
            await asyncio.sleep(remaining)
        else:
            print(f"⚠️ Work took {elapsed_time:.4f}s (exceeded target of {self.second}s). No sleep required.")
        
        return False  # Do not suppress exceptions raised inside the block


# async def fetch_data_from_external_api(client: httpx.AsyncClient, todo_id: int) -> dict:
#     """Fetches a specific todo item. Avoid overriding built-in 'id' name."""
#     try:
#         response = await client.get(f"https://jsonplaceholder.typicode.com/todos/{todo_id}")
#         response.raise_for_status()
#         return response.json()
#     except httpx.HTTPError as e:
#         print(f"❌ Error fetching ID {todo_id}: {e}")
#         return {"id": todo_id, "error": str(e)}


DOWNLOAD_DIR = "downloaded_images"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# async def download_image_from_url(client: httpx.AsyncClient, url: str, file_name:str):
#     file_path = os.path.join(DOWNLOAD_DIR, file_name)
#     try:
#         # 1. Fetch the request normally while following redirects
#         response = await client.get(url, follow_redirects=True)
#         response.raise_for_status()

#         # 2. Read the raw bytes into memory explicitly 
#         image_bytes = response.content

#         # 3. Save the file synchronously 
#         with open(file_path, 'wb') as file:
#             file.write(image_bytes)
            
#         print(f"✅ Successfully downloaded: {file_name}")
#     except httpx.HTTPStatusError as e:
#         print(f"❌ Failed to download {file_name}: Server returned status {e.response.status_code}")
#     except Exception as e:
#         print(f"❌ Downloading failed {file_name}: {e}")


# async def main():
#     print("🚀 Starting block...")
    
#     # Enforce minimum block execution time of 2 seconds
#     async with AsyncTimePass(second=5.0):
#         async with httpx.AsyncClient() as client:
#             url = 'https://picsum.photos/3000/4000'
#             tasks = []

#             for index, _ in enumerate(range(50)):
#                 file_name = f"image-{index}.jpg"
#                 tasks.append(download_image_from_url(client, url, file_name))
            
#             await asyncio.gather(*tasks)
                
#         print("⚡ Executing quick code inside the block...")

#         print("⚡ Executing quick code inside the block...")

#     print("🏁 Block finished, moving on!")

# if __name__ == '__main__':
#     asyncio.run(main())


class SyncTimePass:
    def __init__(self, second: float):
        self.second = second
        self.start_time = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.perf_counter()
        elapsed_time = end_time - self.start_time
        remaining = self.second - elapsed_time

        if remaining > 0:
            print(f"⏱️ Work finished in {elapsed_time:.4f}s. Padding block with a {remaining:.4f}s sleep...")
            time.sleep(remaining)
        else:
            print(f"⚠️ Work took {elapsed_time:.4f}s (exceeded target of {self.second}s). No sleep required.")
        
        return False  # Do not suppress exceptions
    
def download_image_from_url(url: str, file_name: str):
    """Worker function: Each thread creates its own client instance for true concurrency."""
    file_path = os.path.join(DOWNLOAD_DIR, file_name)
    try:
        # Creating the client inside the thread isolates the network pipeline
        with httpx.Client() as client:
            response = client.get(url, follow_redirects=True)
            response.raise_for_status()

            with open(file_path, 'wb') as file:
                file.write(response.content)
            
        print(f"✅ Successfully downloaded: {file_name}")
    except Exception as e:
        print(f"❌ Downloading failed {file_name}: {e}")


def main():
    print("🚀 Starting threaded block...")
    
    with SyncTimePass(second=2.0):
        url = 'https://picsum.photos/3000/4000'
        
        # Max workers set to 5 so all 5 images fire off at the exact same instant
        with ThreadPoolExecutor(max_workers=5) as executor:
            for index in range(5):
                file_name = f"image-{index}.jpg"
                executor.submit(download_image_from_url, url, file_name)
                
        # The script waits here until all threads complete in parallel

        print("⚡ Executing quick code inside the block...")

    print("🏁 Block finished, moving on!")


if __name__ == '__main__':
    main()