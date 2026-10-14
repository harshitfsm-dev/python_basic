#  String Compression
# Example 1:

# Input: chars = ["a","a","b","b","c","c","c"]
# Output: 6
# Explanation: The groups are "aa", "bb", and "ccc". This compresses to "a2b2c3".
# After modifying the input array in-place, the first 6 characters of chars should be ["a","2","b","2","c","3"].


def string_compression(chars: list[str]) -> int:
    write = 0
    read = 0

    while read < len(chars):
        current_char = chars[read]
        count = 0

        # Count consecutive occurrences
        while read < len(chars) and chars[read] == current_char:
            read += 1
            count += 1

        # Write the character
        chars[write] = current_char
        write += 1

        # Write the count digits if count > 1
        if count > 1:
            for c in str(count):
                chars[write] = c
                write += 1

    return write
        

        


input_list = ["a","b","b","b","b","b","b","b","b","b","b","b","b", "c", "c"]
output = string_compression(input_list)
print("Output==>", output)