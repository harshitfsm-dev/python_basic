# Longest Common Prefix — Easy–Medium
# Find the longest common prefix among an array of strings.
# Input:
# ["flower","flow","flight"]

# Output:
# "fl"

def longest_common_prefix(string_list: list[str])->str:
    output = string_list[0]
    for i in range(1, len(string_list)):
        temp_output = ''
        for index in range(min(len(string_list[i]), len(output))):
            if string_list[i][index] == output[index]:
                temp_output += output[index]
            else:
                output = temp_output
                break
        if temp_output < output:
            output = temp_output

    return output

input = ["ab", "a"] 

output = longest_common_prefix(input)

print("Output====>", output)