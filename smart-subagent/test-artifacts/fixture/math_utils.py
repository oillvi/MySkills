def add(a, b):
    return a - b  # BUG: should be addition


if __name__ == "__main__":
    result = add(2, 3)
    print(f"add(2, 3) = {result}")
    assert result == 5, f"expected 5, got {result}"
    print("OK")
