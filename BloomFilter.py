import math
import mmh3


class BloomFilter:
    # To create bit array of size n
    '''
      size - size of bit array calc based the formula
      k    - no. of hash function used to hash the value
      p    - probability of false positive
    '''

    def __init__(self, n):
        self.p = 0.05
        self.size = math.ceil(-n * math.log(self.p) / (math.log(2) ** 2))
        self.k = math.ceil(self.size / n * math.log(2))
        self.bit_array = bytearray(math.ceil(self.size / 8))

    def __set_bit__(self, index):
        byte_index = int(index / 8)
        self.bit_array[byte_index] = self.bit_array[byte_index] | (1 << (7 - index % 8))

    def __get_bit__(self, index):
        byte_index = int(index / 8)
        return self.bit_array[byte_index] & (1 << (7 - index % 8))

    # Func to insert values into BF
    def insert(self, value, freq=1):
        line_hash = str(mmh3.hash(value, freq))
        for i in range(self.k):
            index = mmh3.hash(line_hash, i) % self.size
            self.__set_bit__(index)

    # To check if the value is present in BF or not
    def validate(self, value, freq=1):
        line_hash = str(mmh3.hash(value, freq))
        for i in range(self.k):
            check_at_index = mmh3.hash(line_hash, i) % self.size
            if self.__get_bit__(check_at_index):
                continue
            else:
                return False
        return True

    def readBloomFilterFromFile(self, filename):
        f = open(filename, "rb")
        self.bit_array = bytearray(f.read())
        print(self.bit_array)
        f.close()

    def readBloomFilterFromBytes(self, bf_as_bytes):
        self.bit_array = bytearray(bf_as_bytes)

    # Returns the bit array
    def getBloomFilter(self):
        return self.bit_array

    # Returns the size of the bit array
    def getSize(self):
        return self.size

    def getNFromSize(self, size):
        return math.floor(size * -1 * (math.log(2) ** 2) / math.log(self.p))

    # Returns the # of Hash Functions ie. h1(k), h2(k) ...
    def getNumberOfHashFunctions(self):
        return self.k

    def getAsBytes(self):
        return self.bit_array
