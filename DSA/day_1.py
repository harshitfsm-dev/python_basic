# 1. Two Sum — Easy
# Given an array of integers nums and an integer target, return the indices of the two numbers such that they add up to target.
# Example
# Input:  nums = [2,7,11,15], target = 9
# Output: [0,1]


def get_two_sum(nums: list[int], target: int):
    required_values = {}
    for index, num in enumerate(nums):
        if num in required_values:
            return [required_values[num], index]

        required_values[target - num] = index
    return [-1, -1]


input = [2, 7, 6, 0]
target = 6

# output = get_two_sum(input, target)

# print("output==>", output)


# 2. Contains Duplicate — Easy
# Given an integer array, determine whether any value appears more than once.
# Input:  [1,2,3,1]
# Output: true

# Input:  [1,2,3,4]
# Output: false


def contains_duplicate(nums: list[int]) -> bool:
    present_values = {}
    for index, num in enumerate(nums):
        if num in present_values:
            return True
        present_values[num] = index
    return False


input = [2, 7, 6, 0, 7, 8]

# output = contains_duplicate(input)
# print(output)


# 3. Valid Anagram — Easy
# Given two strings s and t, determine whether t is an anagram of s.
# Input:  s = "listen", t = "silent"
# Output: true

def is_anagram(string1: str, string2: str)->bool:
    if len(string1) != len(string2):
        return False
    # return sorted(s) == sorted(t)
    char_count ={}
    for char in string1:
        if char in char_count:
            char_count[char] += 1

        else:
            char_count[char] = 1
    for char in string2:

        if char in char_count:
            char_count[char] -= 1

        else:
            return False
    
    for val in char_count.values():
        if val != 0:
            return False
        
    return True

s = "listen"
t = "silent"
# s = "anagram"
# t = "nagaram"
output = is_anagram(s,t)
print('output==>>>', output)
