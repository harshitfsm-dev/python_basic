# 15. Reverse Words in a String — Medium
# Given a string containing words separated by spaces, reverse the order of the words.
# Input:
# "the sky is blue"

# Output:
# "blue is sky the"


def reverse_string(string: str):
    # return " ".join(reversed([s for s in string.split(' ') if s != ""]))
    r = len(string) - 1
    output = ""
    while r >= 0:
        word = ""
        while string[r] != " " and r >= 0:
            word = string[r] + word
            r = r - 1
        if word:
            if output:
                output += " " + word
            else:
                output += word
        r = r - 1

    return output


input = "the sky is blue"
output = reverse_string(input)
print("output==>", output)
