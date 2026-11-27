import subprocess
import sys
import time

PREFIX = "clab-netsec-lab"


def run(node, cmd):
    p = subprocess.run(
        ["docker", "exec", f"{PREFIX}-{node}", "sh", "-c", cmd],
        capture_output=True,
        text=True,
    )
    return p.returncode, p.stdout.strip()


def check(name, passed, info=""):
    tag = "PASS" if passed else "FAIL"
    line = f"[{tag}] {name}"
    if info:
        line += f" -- {info}"
    print(line)
    return passed


def check_ospf_neighbors(node, expected):
    rc, out = run(node, 'vtysh -c "show ip ospf neighbor"')
    count = out.count("Full")
    return check(
        f"{node} ospf neighbors",
        rc == 0 and count == expected,
        f"{count}/{expected} Full",
    )


def check_route(node, dst, via):
    rc, out = run(node, f"ip route show {dst}")
    return check(f"{node} route to {dst}", rc == 0 and via in out, f"via {via}")


def check_ping(src, dst):
    rc, _ = run(src, f"ping -c 2 -W 2 {dst}")
    return check(f"ping {src} -> {dst}", rc == 0)


def test_failover():
    print("testing failover: bringing isp-r2 eth1 down...")
    try:
        run("isp-r2", "ip link set eth1 down")
        time.sleep(4)

        _, route = run("isp-r1", "ip route show 4.4.4.4")
        on_backup = "198.51.100.6" in route and "198.51.100.2" not in route
        rc, _ = run("isp-r1", "ping -c 2 -W 2 4.4.4.4")

        return check("ospf failover (r2 -> r3)", on_backup and rc == 0, "backup via 198.51.100.6")
    finally:
        run("isp-r2", "ip link set eth1 up")
        print("restored isp-r2 eth1")


def main():
    checks = [
        check_ospf_neighbors("isp-r1", 2),
        check_ospf_neighbors("isp-r4", 2),
        check_route("isp-r1", "4.4.4.4", "198.51.100.2"),
        check_route("isp-r4", "1.1.1.1", "198.51.100.9"),
        check_ping("isp-r1", "4.4.4.4"),
        check_ping("isp-r4", "1.1.1.1"),
        test_failover(),
    ]

    if not all(checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
