import asyncio
import socket
import subprocess

async def check_adb_port(ip, port=5555, timeout=0.5):
    """检查指定IP是否开放ADB端口"""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout
        )
        writer.close()
        try:
            await writer.wait_closed()
        except AttributeError:
            pass
        return True
    except (asyncio.TimeoutError, OSError, ConnectionError):
        return False


def detect_network_segment():
    """自动获取本机所在的网段前三段"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        local_ip = sock.getsockname()[0]
    except OSError:
        local_ip = "127.0.0.1"
    finally:
        sock.close()

    if local_ip.startswith("127."):
        try:
            host_ips = socket.gethostbyname_ex(socket.gethostname())[2]
        except socket.gaierror:
            host_ips = []
        for candidate in host_ips:
            if candidate and not candidate.startswith("127.") and "." in candidate:
                local_ip = candidate
                break

    parts = local_ip.split(".")
    if len(parts) >= 3:
        return ".".join(parts[:3])
    raise RuntimeError("无法自动识别网段，请手动指定")


async def scan_network(network=None, port=5555, concurrency=100, timeout=0.5):
    """扫描整个网段"""
    network_prefix = network or detect_network_segment()
    semaphore = asyncio.Semaphore(concurrency)
    tasks = []

    async def check_ip(ip_suffix):
        ip = f"{network_prefix}.{ip_suffix}"
        async with semaphore:
            if await check_adb_port(ip, port=port, timeout=timeout):
                return ip
        return None

    for i in range(1, 255):
        tasks.append(asyncio.create_task(check_ip(i)))

    devices = []
    for task in asyncio.as_completed(tasks):
        ip = await task
        if ip:
            devices.append(ip)

    return devices

def connect_adb(ip, port=5555):
    """连接ADB设备"""
    try:
        result = subprocess.run(
            ["adb", "connect", f"{ip}:{port}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return "connected" in result.stdout.lower()
    except (subprocess.SubprocessError, OSError):
        return False

async def adbc():
    subprocess.Popen(["adb", "devices"],stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    try:
        network_prefix = detect_network_segment()
    except RuntimeError as exc:
        print(exc)
        return

    print(f"Scanning for ADB devices on {network_prefix}.0/24...")
    devices = await scan_network(network=network_prefix)

    if not devices:
        print("No ADB devices found.")
        return

    for device in devices:
        print(f"Found device at {device}, connecting...")
        if connect_adb(device):
            print(f"✓ Connected to {device}")
        else:
            print(f"✗ Failed to connect to {device}")

def main():
    asyncio.run(adbc())

if __name__ == "__main__":
    main()
