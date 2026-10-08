# Group Anagrams — Medium
# Given an array of strings, group the anagrams together.
# Input: strs = ["eat","tea","tan","ate","nat","bat"]
# Output: [["bat"],["nat","tan"],["ate","eat","tea"]]
# Example 2:
# Input: strs = [""]
# Output: [[""]]
# Example 3:
# Input: strs = ["a"]
# Output: [["a"]]


def is_group_anagrams(str_list: list[str]) -> list[list[str]]:
    unique_list:dict[list[str]] = {}
    for string in str_list:
        sorted_str = "".join(sorted(string))
        if sorted_str in unique_list:
            unique_list[sorted_str].append(string)
        else:
            unique_list[sorted_str] = [string]
    return [x for x in unique_list.values()]


input = ["eat", "tea", "tan", "ate", "nat", "bat"]
# output = is_group_anagrams(input)
# print("Output===>>>", output)

