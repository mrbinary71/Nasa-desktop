# First install this sources:
#
# Install pil (pip install Pillow)
# Install lxml (pip install lxml)
# Install feh (sudo apt install feh) 
# Install glib (sudo apt-get install python-gtk2)

DOWNLOAD_PATH = '/tmp/backgrounds/'
CUSTOM_FOLDER = 'nasa-apod-backgrounds'
RESOLUTION_TYPE = 'stretch'
RESOLUTION_X = 1024
RESOLUTION_Y = 768
NASA_APOD_SITE = 'http://apod.nasa.gov/apod/'
IMAGE_SCROLL = True
IMAGE_DURATION = 1200
SEED_IMAGES = 10
SHOW_DEBUG = True

import glib
import subprocess
import commands
import urllib
import urllib2
import re
import os
import random
import glob
from PIL import Image
from sys import stdout
from sys import exit
from lxml import etree
from datetime import datetime, timedelta

def find_resolution():
    if RESOLUTION_TYPE == 'default':
        if SHOW_DEBUG:
            print "Using default resolution of %sx%s" % (RESOLUTION_X, RESOLUTION_Y)
        return RESOLUTION_X, RESOLUTION_Y

    res_x = 0
    res_y = 0

    if SHOW_DEBUG:
        print "Attempting to determine the current resolution."
    if RESOLUTION_TYPE == 'largest':
        regex_search = 'connected'
    else:
        regex_search = 'current'
        
    p1 = subprocess.Popen(["xrandr"], stdout=subprocess.PIPE)
    p2 = subprocess.Popen(["grep", regex_search], stdin=p1.stdout, stdout=subprocess.PIPE)
    p1.stdout.close()
    output = p2.communicate()[0]

    if RESOLUTION_TYPE == 'largest':
        # We are going to go through the connected devices and get the X/Y from the largest
        matches = re.finditer(" connected ([0-9]+)x([0-9]+)+", output)
        if matches:
            largest = 0
            for match in matches:
                if int(match.group(1)) * int(match.group(2)) > largest:
                    res_x = match.group(1)
                    res_y = match.group(2)
        elif SHOW_DEBUG:
            print "Could not determine largest screen resolution."
    else:
        reg = re.search(".* current (.*?) x (.*?),.*", output)
        if reg:
            res_x = reg.group(1)
            res_y = reg.group(2)
        elif SHOW_DEBUG:
            print "Could not determine current screen resolution."

    # If we couldn't find anything automatically use what was set for the defaults
    if res_x == 0 or res_y == 0:
        res_x = RESOLUTION_X
        res_y = RESOLUTION_Y
        if SHOW_DEBUG:
            print "Could not determine resolution automatically. Using defaults."

    if SHOW_DEBUG:
        print "Using detected resolution of %sx%s" % (res_x, res_y)

    return int(res_x), int(res_y)

# Uses GLib to find the localized "Downloads" folder
# See: http://askubuntu.com/questions/137896/how-to-get-the-user-downloads-folder-location-with-python
def set_download_folder():
    downloads_dir = glib.get_user_special_dir(glib.USER_DIRECTORY_DOWNLOAD)
    if downloads_dir:
        # Add any custom folder
        new_path = os.path.join(downloads_dir, CUSTOM_FOLDER)
        if SHOW_DEBUG:
            print "Using automatically detected path:", new_path
    else:
        new_path = DOWNLOAD_PATH
        if SHOW_DEBUG:
            print "Could not determine download folder with GLib. Using default."
    return new_path

# Download HTML of the site
def download_site(url):
    if SHOW_DEBUG:
        print "Downloading contents of the site to find the image name"
    opener = urllib2.build_opener()
    req = urllib2.Request(url)
    try:
        response = opener.open(req)
        reply = response.read()
    except urllib2.HTTPError, error:
        if SHOW_DEBUG:
            print "Error downloading " + url + " - " + str(error.code) 
        reply = "Error: " + str(error.code)
    return reply

# Finds the image URL and saves it
def get_image(text):
    if SHOW_DEBUG:
        print "Grabbing the image URL"
    file_url, filename, file_size = get_image_info('a href', text)
    # If file_url is None, the today's picture might be a video
    if file_url is None:
        return None

    if SHOW_DEBUG:
        print "Found name of image:", filename

    save_to = os.path.join(DOWNLOAD_PATH, os.path.splitext(filename)[0] + '.png')

    if not os.path.isfile(save_to):
        # If the response body is less than 500 bytes, something went wrong
        if file_size < 500:
            print "Response less than 500 bytes, probably an error\nAttempting to just grab image source"
            file_url, filename, file_size = get_image_info('img src', text)
            # If file_url is None, the today's picture might be a video
            if file_url is None:
                return None
            print "Found name of image:", filename
            if file_size < 500:
                # Give up
                if SHOW_DEBUG:
                    print "Could not find image to download"
                exit()

        if SHOW_DEBUG:
            print "Retrieving image"
            urllib.urlretrieve(file_url, save_to, print_download_status)

            # Adding additional padding to ensure entire line 
            if SHOW_DEBUG:
                print "\rDone downloading", human_readable_size(file_size), "       "
        else: 
            urllib.urlretrieve(file_url, save_to)
    elif SHOW_DEBUG:
        print "File exists, moving on"

    return save_to

# Resizes the image to the provided dimensions
def resize_image(filename):
    if SHOW_DEBUG:
        print "Opening local image"

    image = Image.open(filename)
    current_x, current_y = image.size
    if (current_x, current_y) == (RESOLUTION_X, RESOLUTION_Y):
        if SHOW_DEBUG:
            print "Images are currently equal in size. No need to scale."
    else: 
        if SHOW_DEBUG:
            print "Resizing the image from", image.size[0], "x", image.size[1], "to", RESOLUTION_X, "x", RESOLUTION_Y
        image = image.resize((RESOLUTION_X, RESOLUTION_Y), Image.ANTIALIAS)

        if SHOW_DEBUG:
            print "Saving the image to", filename
        fhandle = open(filename, 'w')
        image.save(fhandle, 'PNG')

# Sets the new image as the wallpaper
def set_gnome_wallpaper(file_path):
    if SHOW_DEBUG:
        print "Setting the wallpaper"
    command = "feh --bg-fill " + file_path
    status, output = commands.getstatusoutput(command)
    return status

def print_download_status(block_count, block_size, total_size):
    written_size = human_readable_size(block_count * block_size)
    total_size = human_readable_size(total_size)

    # Adding space padding at the end to ensure we overwrite the whole line
    stdout.write("\r%s bytes of %s         " % (written_size, total_size))
    stdout.flush()

def human_readable_size(number_bytes):
    for x in ['bytes', 'KB', 'MB']:
        if number_bytes < 1024.0:
            return "%3.2f%s" % (number_bytes, x)
        number_bytes /= 1024.0

# Creates the necessary XML so background images will scroll through
def create_desktop_background_scoll(filename):
    if not IMAGE_SCROLL:
        return filename

    if SHOW_DEBUG:
        print "Creating XML file for desktop background switching."

    filename = DOWNLOAD_PATH + '/nasa_apod_desktop_backgrounds.xml'

    # Create our base, background element
    background = etree.Element("background")

    # Grab our PNGs we have downloaded
    images = glob.glob(DOWNLOAD_PATH + "/*.png")
    num_images = len(images)

    if num_images < SEED_IMAGES:
        # Let's seed some images
        # Start with yesterday and continue going back until we have enough
        if SHOW_DEBUG:
            print "Downloading some seed images as well"
        days_back = 0
        seed_images_left = SEED_IMAGES
        while seed_images_left > 0:
            days_back+=1
            if SHOW_DEBUG:
                print "Downloading seed image (" + str(seed_images_left) + " left):"
            day_to_try = datetime.now() - timedelta(days=days_back)

            # Filenames look like /apYYMMDD.html
            seed_filename = NASA_APOD_SITE + "ap" + day_to_try.strftime("%y%m%d") + ".html"
            seed_site_contents = download_site(seed_filename)

            # Make sure we didn't encounter an error for some reason
            if seed_site_contents == "error":
                continue

            seed_filename = get_image(seed_site_contents)
            # If the content was an video or some other error occurred, skip the
            # rest.
            if seed_filename is None:
                continue

            resize_image(seed_filename)

            # Add this to our list of images
            images.append(seed_filename)
            seed_images_left-=1
        if SHOW_DEBUG:
            print "Done downloading seed images"

    # Get our images in a random order so we get a new order every time we get a new file
    random.shuffle(images)
    # Recalculate the number of pictures
    num_images = len(images)

    for i, image in enumerate(images):
        # Create a static entry for keeping this image here for IMAGE_DURATION
        static = etree.SubElement(background, "static")

        # Length of time the background stays
        duration = etree.SubElement(static, "duration")
        duration.text = str(IMAGE_DURATION)

        # Assign the name of the file for our static entry
        static_file = etree.SubElement(static, "file")
        static_file.text = images[i]

        # Create a transition for the animation with a from and to
        transition = etree.SubElement(background, "transition")

        # Length of time for the switch animation
        transition_duration = etree.SubElement(transition, "duration")
        transition_duration.text = "5"

        # We are always transitioning from the current file
        transition_from = etree.SubElement(transition, "from")
        transition_from.text = images[i]

        # Create our tranition to element
        transition_to = etree.SubElement(transition, "to")

        # Check to see if we're at the end, if we are use the first image as the image to
        if i + 1 == num_images:
            transition_to.text = images[0]
        else:
            transition_to.text = images[i + 1]

    xml_tree = etree.ElementTree(background)
    xml_tree.write(filename, pretty_print=True)

    return filename

def get_image_info(element, text):
    # Grabs information about the image
    regex = '<' +  element + '="(image.*?)"'
    reg = re.search(regex, text, re.IGNORECASE)
    if reg:
        if 'http' in reg.group(1):
            # Actual URL
            file_url = reg.group(1)
        else:
            # Relative path, handle it
            file_url = NASA_APOD_SITE + reg.group(1)
    else: 
        if SHOW_DEBUG:
            print "Could not find an image. May be a video today."
        return None, None, None

    # Create our handle for our remote file
    if SHOW_DEBUG:
        print "Opening remote URL"
        
    remote_file = urllib.urlopen(file_url)

    filename = os.path.basename(file_url)
    file_size = float(remote_file.headers.get("content-length"))

    return file_url, filename, file_size

if __name__ == '__main__':
    # Our program
    if SHOW_DEBUG: 
        print "Starting"

    # Find desktop resolution
    RESOLUTION_X, RESOLUTION_Y = find_resolution()

    # Set a localized download folder
    DOWNLOAD_PATH = set_download_folder()

    # Create the download path if it doesn't exist
    if not os.path.exists(os.path.expanduser(DOWNLOAD_PATH)):
        os.makedirs(os.path.expanduser(DOWNLOAD_PATH))

    # Grab the HTML contents of the file 
    site_contents = download_site(NASA_APOD_SITE)
    if site_contents == "error":
        if SHOW_DEBUG:
            print "Could not contact site."
        exit()

    # Download the image
    filename = get_image(site_contents)
    if filename is not None:
        # Resize the image
        resize_image(filename)

    # Create the desktop switching xml
    # filename = create_desktop_background_scoll(filename)
    # If the script was unable todays image and IMAGE_SCROLL is set to False,
    # the script exits
    if filename is None:
        if SHOW_DEBUG:
            print "Today's image could not be downloaded."
        exit()

    # Set the wallpaper
    status = set_gnome_wallpaper(filename)
    if SHOW_DEBUG:
        print "Finished!"

