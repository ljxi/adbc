import asyncio
import socket
import subprocess
import threading

from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf

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

async def discover_mdns_devices(timeout=3):
    """通过 mDNS 发现 ADB 无线调试设备"""
    devices = []
    lock = threading.Lock()

    def on_service_state_change(zeroconf, service_type, name, state_change):
        if state_change is ServiceStateChange.Added:
            info = zeroconf.get_service_info(service_type, name)
            if info and info.addresses:
                ip = socket.inet_ntoa(info.addresses[0])
                port = info.port
                with lock:
                    devices.append((ip, port))

    def run_browser():
        zc = Zeroconf()
        browser = ServiceBrowser(zc, "_adb-tls-connect._tcp.local.", handlers=[on_service_state_change])
        threading.Event().wait(timeout)
        browser.cancel()
        zc.close()

    await asyncio.to_thread(run_browser)
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

    print(f"Scanning for ADB devices on {network_prefix}.0/24 + mDNS...")
    tcp_devices, mdns_devices = await asyncio.gather(
        scan_network(network=network_prefix),
        discover_mdns_devices(),
    )

    # 合并去重：以 ip:port 为 key
    seen = set()
    all_devices = []

    for ip in tcp_devices:
        key = f"{ip}:5555"
        if key not in seen:
            seen.add(key)
            all_devices.append((ip, 5555))

    for ip, port in mdns_devices:
        key = f"{ip}:{port}"
        if key not in seen:
            seen.add(key)
            all_devices.append((ip, port))

    if not all_devices:
        print("No ADB devices found.")
        return

    for ip, port in all_devices:
        print(f"Found device at {ip}:{port}, connecting...")
        if connect_adb(ip, port):
            print(f"✓ Connected to {ip}:{port}")
        else:
            print(f"✗ Failed to connect to {ip}:{port}")

def main():
    asyncio.run(adbc())

if __name__ == "__main__":
    main()
