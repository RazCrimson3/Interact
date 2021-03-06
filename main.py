import argparse
import os
import sys
import time
from math import floor, log

from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer

from progress.bar import Bar

from BloomFilter import BloomFilter
from P2P.Server import NetworkManager
from P2P import utils
import Synchronizer

# Create the parser
my_parser = argparse.ArgumentParser(description='Sync two files')

# Add the arguments
my_parser.add_argument('Path',
                       metavar='path',
                       type=str,
                       help='the file path to sync')


my_parser.add_argument('--host', action='store_true',
                       help='sets the current the user as host')

# Execute the parse_args() method
args = my_parser.parse_args()

input_path = args.Path
input_path = os.path.abspath(input_path)
role = 1 if args.host else 0

my_missing_content = {}
should_trigger_modified = True


class RequestReceivedHandler:
    def handle_request(self, request):
        global my_missing_content, should_trigger_modified
        if(request.get_type() == utils.Request.REQUEST_TYPE_BLOOMFILTER):
            # The opposite party has sent its bloom filter and now requesting ours
            # We send it now
            print("\n\nThe other user has modified his file, syncing...")
            print("Received the bloom filter")
            my_missing_content = getMissingContent(getNFromByteSize(
                request.get_message_size()), request.get_message_bytes())
            print("Acknowleding and transmitting the bloom filter...")
            bf = computeBloomFilter()
            req = utils.Request(
                utils.Request.REQUEST_TYPE_REPLY_SLAVE_BLOOMFILTER, bf.getAsBytes())
            p2p.send_request(req)

        elif(request.get_type() == utils.Request.REQUEST_TYPE_REPLY_SLAVE_BLOOMFILTER):
            print(
                "Request was acknowledged by the other peer and has given the other bloom filter")
            my_missing_content = getMissingContent(getNFromByteSize(
                request.get_message_size()), request.get_message_bytes())

            # Send the missing contents computed to the other user
            print("Sending the actual changed lines ...")
            req = utils.Request(
                utils.Request.REQUEST_SEND_ACTUAL_LINES, str(my_missing_content))
            p2p.send_request(req)

        elif(request.get_type() == utils.Request.REQUEST_SEND_ACTUAL_LINES):
            print("Received the actual missing lines...")
            missing_dict = eval(request.get_message_bytes())
            should_trigger_modified = False
            print("Syncing the file...")
            Synchronizer.syncFile(
                input_path, my_missing_content, missing_dict)
            print("Verifying that the file is up-to-date ...")
            print("Verifying hash...")
            final_hash = Synchronizer.computeHash(input_path)
            req = utils.Request(
                utils.Request.REQUEST_SEND_ENTIRE_FILE_HASH, final_hash)
            p2p.send_request(req)
            print("Done.")
            time.sleep(1)
            should_trigger_modified = True

        elif(request.get_type() == utils.Request.REQUEST_SEND_ENTIRE_FILE_HASH):
            print("Received the hash from the other side ...")
            print("Verifying hash...")
            hash_from_other_user = request.get_message_bytes()
            our_hash = Synchronizer.computeHash(input_path)

            if hash_from_other_user == our_hash:
                print("Done verifying hash.")
            else:
                req = utils.Request(
                    utils.Request.REQUEST_SEND_ENTIRE_FILE, read_entire_file())
                p2p.send_request(req)
            print("Done.")
        elif(request.get_type() == utils.Request.REQUEST_SEND_ENTIRE_FILE):
            file_content_from_other_user = request.get_message_bytes()
            should_trigger_modified = False

            with open(input_path, 'wb') as f:
                f.write(file_content_from_other_user)
            time.sleep(1)
            should_trigger_modified = True
            print("Done.")


rh = RequestReceivedHandler()
p2p = NetworkManager(rh)

if not os.path.isfile(input_path):
    print('\n', input_path, '- Not a valid file to stage for syncing')
    sys.exit()


def on_modified(event):
    if (os.path.abspath(event.src_path) == input_path) and should_trigger_modified:
        # Detect changes from only the given path.
        # Ignore all other changes
        print("\n\nDetected changes - ",
              event.src_path, "py has been modified...")
        initiateSync()


class FileEventHandler(PatternMatchingEventHandler):
    def __init__(self, patterns=None, ignore_patterns=None, ignore_directories=False, case_sensitive=False,
                 on_modified_callback=on_modified):
        self.on_modified_callback = on_modified_callback
        self.last_modified = time.time()
        return super().__init__(patterns=patterns, ignore_patterns=ignore_patterns,
                                ignore_directories=ignore_directories, case_sensitive=case_sensitive)

    def on_modified(self, event):
        if(time.time() - self.last_modified) > 1:
            self.on_modified_callback(event)
            self.last_modified = time.time()
        return super().on_modified(event)


# Use this func to find n required for BloomFilter
# byte_size is the len of bloomfilter bit array in bytes
def getNFromByteSize(byte_size):
    return floor((byte_size * 8)*-1*(log(2)**2)/log(0.05))


def main():
    print("\nInteract [Version 1.0]")
    print("GNU GENERAL PUBLIC LICENSE\nVersion 3, 23 Oct 2019\n")
    patterns = "*"
    ignore_patterns = ["*.save"]
    ignore_directories = True
    case_sensitive = True
    file_event_handler = FileEventHandler(patterns, ignore_patterns, ignore_directories,
                                          case_sensitive, on_modified_callback=on_modified)

    path = "."
    go_recursively = True
    my_observer = Observer()
    my_observer.schedule(file_event_handler, path, recursive=go_recursively)

    my_observer.start()

    if role == 1:
        progress = Bar("Creating Server")
        for i in range(10):
            time.sleep(0.05)
            progress.next(10)
        progress.finish()
        p2p.create_host()
        initiateSync()
    else:

        ip = input("Enter the IP of the host: ")
        port = int(input("Enter the PORT of the host: "))
        progress = Bar("Initiating Connection")
        for i in range(10):
            # Do some work
            time.sleep(0.05)
            progress.next(10)
        progress.finish()
        p2p.create_client(ip, port)

    print("Observing ", input_path, "for changes...")

    try:
        while True:
            # This handles the request appropriately
            a = p2p.check_if_incoming_data()
            # request_type, request_data = a[0], a[1]
            time.sleep(1)
    except KeyboardInterrupt:
        my_observer.stop()
        my_observer.join()


def computeBloomFilter():
    filename = input_path

    # total # of line in the file
    user_file_NOL = 0

    # content frequency
    user_file_content = {}

    with open(filename) as user_file:
        for line in user_file:
            user_file_NOL += 1
    # creates bloomfilter of required size
    bloom_filter = BloomFilter(user_file_NOL)

    # read contents of file and insert into BF
    with open(filename) as user_file:
        for line in user_file:
            try:
                user_file_content[line] += 1
            except:
                user_file_content[line] = 1
            bloom_filter.insert(line, freq=user_file_content[line])

    return bloom_filter


def getMissingContent(n, bloomfilter_bytes):
    missing_content = {}
    receivedBF = BloomFilter(n)
    receivedBF.readBloomFilterFromBytes(bloomfilter_bytes)
    user_file_content = {}
    line_number = 0
    with open(input_path) as user_file:
        for line in user_file:
            line_number += 1
            try:
                user_file_content[line] += 1
            except:
                user_file_content[line] = 1
            if not receivedBF.validate(line, freq=user_file_content[line]):
                missing_content[line_number] = line
    return(missing_content)


def initiateSync():
    print("Redrawing the bloom filter ...")
    bf = computeBloomFilter()
    print("Sending the bloom filter ...")
    req = utils.Request(
        utils.Request.REQUEST_TYPE_BLOOMFILTER, bf.getAsBytes())
    p2p.send_request(req)


def read_entire_file():
    with open(input_path, "rb") as f:
        content = f.read()
        return content


if __name__ == "__main__":
    main()
