import os
import time
import zipfile

import grequests
import vk_api
from termcolor import colored
from functools import wraps

from vk_api import VkUpload
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id


class Bot:
    __slots__ = ("vk_session", "vk", "long_poll", "upload", "event", "messages_data")

    @staticmethod
    def get_token():
        with open("token", "r") as f:
            return f.readline()

    def __init__(self):
        self.vk_session = vk_api.VkApi(token=Bot.get_token())
        self.vk = self.vk_session.get_api()
        self.long_poll = VkLongPoll(self.vk_session)
        self.upload = VkUpload(self.vk_session)
        self.event = None
        self.messages_data = None

    def send_message(self, message, attachment=None):
        if not attachment:
            self.vk.messages.send(
                user_id=self.event.user_id,
                random_id=get_random_id(),
                message=message
            )
        else:
            self.vk.messages.send(
                user_id=self.event.user_id,
                attachment=attachment,
                random_id=get_random_id(),
                message=message
            )

    def get_messages_data(self):
        messages_data = self.vk_session.method(
            'messages.getById',
            {'message_ids': {self.event.message_id}}
        )
        self.messages_data = messages_data['items'][0]

    def get_photos_links(self):
        # print("in get_photos_links")
        res = []
        for a in self.messages_data['attachments']:
            # print("in get_photos_links attachments")
            if 'photo' in a:
                s = sorted(a['photo']['sizes'], key=lambda x: x['width'])
                # print(colored("s", "green"))
                # pprint(s)
                res.append(s[-1]['url'])
                # print(colored("res", "green"))
                # pprint(res)
        if 'reply_message' in self.messages_data:
            print("in get_photos_links reply")
            self.messages_data = self.vk_session.method(
                'messages.getById',
                {'message_ids': {self.messages_data['reply_message']['id']}}
            )

            self.messages_data = self.messages_data['items'][0]
            res.extend(self.get_photos_links())
        if 'fwd_messages' in self.messages_data and self.messages_data['fwd_messages']:
            # print("in get_photos_links fwd")
            for m in self.messages_data['fwd_messages']:
                self.messages_data = m
                res.extend(self.get_photos_links())
        return res


def zip_dir(path, zip_f):
    # zip_f is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            zip_f.write(os.path.join(root, file))


def downloading(links, muid, bot):
    print("in downloading")

    responses = grequests.map((grequests.get(u, stream=True) for u in links))
    unsuccessful_attempt = []

    for ind, response in enumerate(responses):
        print(f"{ind=}")

        if not response or not response.ok:
            print(f"[{ind=}] {response=}")
            unsuccessful_attempt.append(ind + 1)
            continue
        with open(os.path.join('data', muid, str(ind) + '.jpg'), 'wb') as handle:
            for block in response.iter_content(1024):
                if not block:
                    break
                handle.write(block)
    if unsuccessful_attempt:
        bot.send_message(
            f"Sorry, there are no photo(s) {', '.join(map(str, unsuccessful_attempt))} in the archive, you can try again.")


def time_logger(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        start = time.monotonic()
        func(*args, **kwargs)
        run_time = time.monotonic() - start
        print(f"It takes {run_time} seconds")

    return wrapped


@time_logger
def bot_logic(bot, event):
    # print(colored("{}: id{}: \"{}\"'.format(event.message_id, event.user_id, event.text)", "green"))
    print('{}: id{}: "{}"'.format(event.message_id, event.user_id, event.text))
    bot.event = event
    if event.text == '':
        bot.send_message(
            "Message text is required. Please enter a name of archive and resend your message."
        )
        return

    bot.get_messages_data()
    links = bot.get_photos_links()

    if len(links) == 0:
        bot.send_message("No photos")
        return

    muid = str(event.user_id) + str(event.message_id)
    pics_path = os.path.join('data', muid)
    if not os.path.exists(pics_path):
        os.makedirs(pics_path)

    downloading(links, muid, bot)

    zip_name = os.path.join('data', str(muid) + ".zip")
    zip_f = zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED)
    zip_dir(pics_path, zip_f)
    zip_f.close()

    doc = bot.upload.document_message(doc=zip_name, title=event.text + str(muid) + ".zip",
                                      peer_id=event.peer_id)
    doc = doc['doc']
    bot.send_message(
        message="Ok. Done",
        attachment='doc{}_{}'.format(doc['owner_id'], doc['id']),
    )

    print('ok')


def main():
    print(colored("Starting", "green"))

    bot = Bot()

    for event in bot.long_poll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            bot_logic(bot, event)


if __name__ == '__main__':
    main()
