# Input: nums = [2,7,11,15], target = 9
# Output: [0,1]

# nums = [3,7,11,2,15,4]
# target = 10


# def two_sum(nums: list[int], target: int):
#     for i, value in enumerate(nums):
#         for j in range(i, len(nums)):
#             if value + nums[j] == target:
#                 return [i, j]
#     return []

# print(two_sum(nums, target))


# def calculate_two_some(nums: list[int], target: int):
#         map_list = {}
#         for i, value in enumerate(nums):
           
#             if value in map_list:
#                   return [i, map_list[value]]
#             map_list[target - value] = i

#         return map_list 


# print(calculate_two_some(nums, target))


# Input: strs = ["flower","flow","flight"]
# Output: "fl"
# strs = ["flower","flow","flight"]


# def get_longest_prefix(str_list: list[str]) -> str:
#     output = str_list[0]
#     for i in range(1, len(str_list)):
#         temp = ''
#         for j, char in enumerate(str_list[i]):
#             if len(output) > j:
#                 if char == output[j]:
#                     temp +=char
#                 else:
#                     break

#         output = temp
#     return output


# print(get_longest_prefix(strs))

# Input: nums = [0,0,1,1,1,2,2,3,3,4]
# Output: 5, nums = [0,1,2,3,4,_,_,_,_,_]


# nums = [0,1,1,0,1,2,2,2,3,3,4]

# def remove_duplicates(nums: list[int]) -> int:
#     if not nums:  # Handle empty list case
#             return 0

#     j = 0  
#     for i in range(1, len(nums)):
#         if nums[j] != nums[i]:
#             j += 1  
#             nums[j] = nums[i]  

#     return j + 1 

# print(remove_duplicates(nums))

# def remove_value(nums: list[int], value: int):
#     if not nums:
#         return 0
    
#     j = 0
#     for i in range(len(nums)):
#         if nums[j] != value:
#             j += 1
#         else:
#             nums.pop(j)
#     return j

# print(remove_value(nums, 3))

# Example 1:

# Input: nums = [1,3,5,6], target = 5
# Output: 2
# Example 2:

# Input: nums = [1,3,5,6], target = 2
# Output: 1


# nums = [1,3,5,6]
# target = 6

# def find_target_index(nums: list[int], target: int) -> int:
#     if nums[0] > target:
#         return 0
    
#     for i in range(len(nums)):
#         if nums[i] >= target:
#             return i
        
#     return len(nums)
        

# print(find_target_index(nums, target))

# Input: digits = [1,2,3]
# Output: [1,2,4]
# digits = [1,2,9]

# def plus_one(digits: list[int]):
#     # digit_str = "".join(map(str, digits))
#     # incremented_int =  int(digit_str) + 1
#     # # return list(map(int,list(str(incremented_int))))
#     # return [int(x) for x in list(str(incremented_int))]

#     for i in range(len(digits)-1, -1, -1):
#             print(i)
#             # If the current digit is 9, set it to 0
#             if digits[i] == 9:
#                 digits[i] = 0
#             else:
#                 # If the current digit is not 9, increment it by 1 and return the list
#                 digits[i] = digits[i] + 1
#                 return digits
#         # If all digits are 9, prepend 1 to the list
#     return [1] + digits

# print(plus_one(digits))


# Input: nums1 = [1,2,3,0,0,0], m = 3, nums2 = [2,5,6], n = 3
# Output: [1,2,2,3,5,6]

# nums1 = [1,3,4,0,0,0]
# m = 3
# nums2 = [0,2,6]
# n = 3

# def merge_array(nums1: list[int], m: int, nums2: list[int], n: int):
#     index_1 = m - 1
#     index_2 = n - 1
#     k = m + n - 1
#     while index_2 >= 0:
#         if index_1 >= 0 and nums1[index_1] > nums2[index_2]:
#             nums1[k] = nums1[index_1]
#             index_1 -= 1
#         else:
#             nums1[k] = nums2[index_2]
#             index_2 -= 1

#         k -= 1
#     return nums1
         
    

# print(merge_array(nums1, m, nums2, n))



#move all zeros to the end [0,30,3,0,5,8,0]

# nums = [0,2,1,0,30,3,0,5,8,0]

# def move_zero_to_the_end(nums: list[int]) -> list[int]:
#     left = 0
#     for i in range(len(nums)):
#         if nums[left] != 0:
#             left += 1
#             continue

#         if nums[left] == 0 and nums[i] != 0:
#             temp = nums[i]
#             nums[i] = nums[left]
#             nums[left] = temp
#             left += 1
        
#     return nums

# print(move_zero_to_the_end(nums))

# Input: prices = [7,1,5,3,6,4]
# Output: 5
# prices = [7,1,5,3,6,1,4, 9]

# def find_best_time(prices: list[int]):
#     max_profit = 0
#     max_price = 0
#     for i in range(len(prices) -1, -1, -1):
#         if prices[i] > max_price:
#             max_price = prices[i]
#         if max_price - prices[i] > max_profit:
#             max_profit = max_price - prices[i]

#     return max_profit

        


# print(find_best_time(prices))


# nums =[4,1,2,1,2]

# def find_single_number(nums: list[int]) -> int:
#     for _ in range(len(nums)):
#         temp = nums[0]
#         nums.pop(0)
#         if temp in nums:
#             nums.append(temp)
#         else:
#             return temp
#     return 0



# print(find_single_number(nums))

# list1 = [1, 2, 3, 4, 5]
# list2 = [4, 5, 6, 7, 8]

# # Returns a set of common items: {4, 5}
# common_items = set(list1) & set(list2)

# # Convert back to a list if needed
# common_list = list(common_items)
# print(common_items)
# print(common_list[0])

# matrix = [[1,10,4,2],[9,3,8,7],[15,16,17,12]]

# def find_lucky_number(matrix: list[list[int]]):
#     min_row = []
#     max_col = []
#     for i in range(len(matrix)):
#         min_num = min(matrix[i])
#         min_row.append(min_num)

#     for i in range(len(matrix[0])):
#         temp_max = 0
#         for j in range(len(matrix)):
#             if matrix[j][i] > temp_max:
#                 temp_max =  matrix[j][i]
        
#         max_col.append(temp_max)
#     common_num = set(min_row) & set(max_col)
#     return list(common_num)[0]

# print(find_lucky_number(matrix))

# Input: nums = [1,7,3,6,5,6]
# Output: 3
# nums = [-1,-1,-1,-1,-1,0]

# def find_pivot_index(nums: list[int]) -> int:
#     left_sum = 0
#     right_sum = sum(nums)
    
#     for i, num in enumerate(nums):
#         right_sum -= num

#         # if left_sum > right_sum:
#         #     return -1
#         if left_sum == right_sum:
#             return i
        
#         left_sum +=  num
        
#     return -1


# print(find_pivot_index(nums))

# Input: height = [1,8,6,2,5,4,8,3,7]
# Output: 49

# height = [1,8,6,2,5,4,8,3,7]

# def find_max_water(height: list[int]):
#     left = 0
#     right = len(height) - 1
#     max_left = height[0]
#     max_right = height[len(height) - 1]
#     max_water = height[max_left] * height[max_right]
    
#     for _ in range(1, len(height), 1):
#         diff = right - left
#         if height[left] 
       
           

#     # print(max_left)
#     # print(max_right)
    
#     return max_water
        


# print(find_max_water(height))

# Input: s = "anagram", t = "nagaram"

# Output: true


# Input: s = "abcd", t = "abcde"
# Output: "e"
# s = "abcd"
# t = "abcde"

# def find_new_character(s: str, t:str):
#     counting = {}
#     for char in s:
#         if char in counting:
#             counting[char] += 1
#         else:
#             counting[char] = 1

#     for char in t:
#         if char not in counting:
#             return char
#         else:
#             counting[char] -= 1
    
#     for char in counting:
#         if counting[char] != 0:
#             return char
# print(find_new_character(s,t))