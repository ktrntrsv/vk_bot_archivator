import os
import time
import zipfile
import grequests
from termcolor import colored
from pprint import pprint

import vk_api
from vk_api import VkUpload
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id


def get_token():
    with open("token", "r") as f:
        return f.readline()


def get_photos_links(msg, vk_session):
    print("in get_photos_links")
    res = []
    print(colored("msg", "red"))
    pprint(msg)
    for a in msg['attachments']:
        print("in get_photos_links attachments")
        if 'photo' in a:
            # pprint([s['url'] for s in a['photo']['sizes'] if s['type'] == 'z'])
            s = sorted(a['photo']['sizes'], key=lambda x: x['width'])
            print(colored("s", "red"))
            pprint(s)
            res.append(s[-1]['url'])
            print(colored("res", "red"))
            pprint(res)
    if 'reply_message' in msg:
        print("in get_photos_links reply")
        messages_data = vk_session.method(
            'messages.getById',
            {'message_ids': {msg['reply_message']['id']}}
        )
        print(colored("message_data", "red"))
        pprint(messages_data)
        messages_data = messages_data['items'][0]
        res.extend(get_photos_links(messages_data))
    if msg['fwd_messages']:
        print("in get_photos_links fwd")
        for m in msg['fwd_messages']:
            res.extend(get_photos_links(m))
    return res


def zip_dir(path, zip_f):
    # zip_f is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            zip_f.write(os.path.join(root, file))


def downloading(links, muid):
    responses = grequests.map((grequests.get(u, stream=True) for u in links))

    for c, response in enumerate(responses):
        print("c: ", c)
        if not response.ok:
            print(response)
            continue
        with open(os.path.join('data', muid, str(c) + '.jpg'), 'wb') as handle:
            for block in response.iter_content(1024):
                if not block:
                    break
                handle.write(block)


def main():
    start = time.time()

    vk_session = vk_api.VkApi(token=get_token())
    vk = vk_session.get_api()
    long_poll = VkLongPoll(vk_session)
    upload = VkUpload(vk_session)

    print(colored("Starting", "red"))

    for event in long_poll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            print(colored("event.__dict__", "red"))
            pprint(event.__dict__)
            print(colored("{}: id{}: \"{}\"'.format(event.message_id, event.user_id, event.text)", "red"))
            print('{}: id{}: "{}"'.format(event.message_id, event.user_id, event.text))

            if event.text == '':
                vk.messages.send(
                    user_id=event.user_id,
                    random_id=get_random_id(),
                    message='Message text is required. Please enter a name or archive and resend your message.'
                )
                continue

            messages_data = vk_session.method(
                'messages.getById',
                {'message_ids': {event.message_id}}
            )
            print(colored("messages_data", "red"))
            pprint(messages_data)
            messages_data = messages_data['items'][0]

            links = get_photos_links(messages_data, vk_session)
            print("links: ", links)
            print("len = ", len(links))

            if len(links) == 0:
                vk.messages.send(
                    user_id=event.user_id,
                    random_id=get_random_id(),
                    message='No photos'
                )
                continue

            muid = str(event.user_id) + str(event.message_id)
            pics_path = os.path.join('data', muid)
            if not os.path.exists(pics_path):
                os.makedirs(pics_path)

            downloading(links, muid)

            zip_name = os.path.join('data', str(muid) + ".zip")
            zip_f = zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED)
            zip_dir(pics_path, zip_f)
            zip_f.close()

            doc = upload.document_message(doc=zip_name, title=event.text + str(muid) + ".zip", peer_id=event.peer_id)
            doc = doc['doc']
            print(colored("doc", "red"))
            pprint(doc)
            vk.messages.send(
                user_id=event.user_id,
                attachment='doc{}_{}'.format(doc['owner_id'], doc['id']),
                random_id=get_random_id(),
                message='Ok. Done.'
            )

            print('ok')
            print(f"It takes {time.time() - start} seconds")


if __name__ == '__main__':
    main()
