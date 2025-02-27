import requests

proxy = "83.149.70.159:13012"
try:
    response = requests.get("https://httpbin.org/ip", proxies={"http": f"http://{proxy}", "https": f"http://{proxy}"}, timeout=10)
    print(response.text)
except requests.RequestException as e:
    print(f"Proxy test failed: {e}")
