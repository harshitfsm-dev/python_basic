# Given a string s containing just the characters '(', ')', '{', '}', '[' and ']', determine if the input string is valid.

# An input string is valid if:

# Open brackets must be closed by the same type of brackets.
# Open brackets must be closed in the correct order.
# Every close bracket has a corresponding open bracket of the same type.


def is_valid_string(string: str) -> bool:
    open_list = []
    for char in string:
        if char == "(" or char == "{" or char == "[":
            open_list.append(char)
        elif len(open_list) == 0:
            return False
        elif (
            char == "}"
            and open_list[-1] == "{"
            or char == "]"
            and open_list[-1] == "["
            or char == ")"
            and open_list[-1] == "("
        ):
            open_list.pop()
        else:
            return False

    return len(open_list) == 0


input = "]()"
output = is_valid_string(input)
print("Output==>", output)
