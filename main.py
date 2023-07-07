import os
import logging
from datetime import datetime
import tarfile
import telebot

logging.basicConfig(level=logging.DEBUG)

BOT_TOKEN: str = os.environ.get('BOT_TOKEN')
if (not BOT_TOKEN):
    logging.critical("Input token is empty!")
    raise Exception("Invalid BOT_TOKEN")
else:
    logging.debug("BOT_TOKEN: [" + BOT_TOKEN + "]")

# Get destination chat
BOT_DEST: str = os.environ.get('BOT_DEST')
if (not BOT_DEST):
    logging.critical("Destination chat is empty!")
    raise Exception("Invalid BOT_DEST")
else:
    BOT_DEST: int = int(BOT_DEST)
    logging.debug("BOT_TOKEN: [" + str(BOT_DEST) + "]")

bot = telebot.TeleBot(BOT_TOKEN)

# Get volumes root path
ROOT_DIR: str = os.environ.get('ROOT_DIR')
if (not ROOT_DIR):
    # Common volumes locations
    ROOT_DIR = ["/var/snap/docker/common/var-lib-docker/volumes/", "/var/lib/docker/volumes", "/root/backup"]
    logging.warning("ROOT_DIR is empty, falling back to default path(s): " + str(ROOT_DIR))
else:
    # Get directories from environment
    ROOT_DIR = [str(x).split() for x in ROOT_DIR.split(",")]

# Get temporary path
TMP_DIR: str = os.environ.get('TMP_DIR')
if (not TMP_DIR):
    TMP_DIR = "/tmp"
    logging.warning("TMP_DIR is empty, falling back to default path: [" + TMP_DIR + "]")
TMP_DIR = os.path.join(TMP_DIR, datetime.now().strftime("%Y%m%d_%H%M%S"))
logging.debug("TMP_DIR: [" + TMP_DIR + "]")

# Function to compress a folder
def MakeTar(source_dir, output_filename):
    logging.debug("Compressing: [" + source_dir + "] to: [" + output_filename + "]")
    try:
        with tarfile.open(output_filename, "w:gz") as tar:
            tar.add(source_dir, arcname=os.path.basename(source_dir))
        return True
    except:
        return False

if __name__ == '__main__':
    # Create temporary output path
    if not os.path.exists(TMP_DIR):
        logging.info("Creating: [" + TMP_DIR + "] folder")
        os.mkdir(TMP_DIR)
    else:
        logging.warning("Folder: [" + TMP_DIR + "] already exists, this could cause some troubles")
    # Process path(s) list
    for singleLocation in ROOT_DIR:
        try:
            # Check if we can access that folder
            subFolders = os.listdir(singleLocation)
        except FileNotFoundError:
            logging.warning("Cannot access path: [" + singleLocation + "]")
            continue
        # If the path exists
        for singleSubfolder in subFolders:
            folderToCompress = os.path.join(singleLocation, singleSubfolder)
            # Check if it is a folder
            if os.path.isdir(folderToCompress):
                logging.debug("Found valid folder: " + folderToCompress)
                archiveName = singleSubfolder + "-" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".tar.gz"
                outputPath = os.path.join(TMP_DIR, archiveName)
                if (MakeTar(folderToCompress, outputPath)):
                    logging.info("Succesfully compressed: [" + outputPath + "]")
                    # Send archive
                    try:
                        bot.send_document(BOT_DEST, open(outputPath, 'rb'))
                        logging.debug("Document: [" + outputPath + "] was sent succesfully")
                    except Exception as retEx:
                        logging.error("Cannot send document: [" + str(retEx) + "]")
                    # Delete archive
                    try:
                        os.remove(outputPath)
                        logging.debug("File: [" + outputPath + "] was deleted succesfully")
                    except Exception as retEx:
                        logging.error("Error while deleting: [" + retEx + "]")
                else:
                    logging.error("Cannot compress: [" + outputPath + "]")
    # Done, bye!
    logging.info("Completed!")