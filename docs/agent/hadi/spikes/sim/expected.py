# [AI-GENERATED: Claude Code]
"""Host-side expected values for demo.c. Prints name=value lines."""
N = 64


def s16(x):
    """Wrap to signed 16-bit. Args: x int. Returns: int."""
    x &= 0xFFFF
    return x - 0x10000 if x & 0x8000 else x


A = [s16(i * 1000 + 12345 - i * 7) for i in range(N)]
B = [s16(30000 - s16(i * 997)) for i in range(N)]
checksum = sum((a & 0xFFFF) * (i + 1) for i, a in enumerate(A)) & 0xFFFFFFFF
dot = s16_32 = sum(a * b for a, b in zip(A, B))
dot = ((dot + 2**31) % 2**32) - 2**31

if __name__ == "__main__":
    print(f"result_checksum={checksum}")
    print(f"result_dot={dot}")
    print("result_done=1")
# [END AI-GENERATED]
