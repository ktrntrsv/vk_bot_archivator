import vk_api
from vk_api import VkUpload
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
import urllib.request
from pprint import pprint
import zipfile

import os

def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file))


vk_session = vk_api.VkApi(token='<выигрываем в информационную безопасность>')


def main():
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)
    upload = VkUpload(vk_session)

    print("Started")

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me and event.text:
            pprint(event.__dict__)
            print('{}: id{}: "{}"'.format(event.message_id, event.user_id, event.text))

            if(event.text == ''):
                vk.messages.send(
                    user_id=event.user_id,
                    random_id=get_random_id(),
                    message='Message text is required. Please enter a name or archive and resend your message.'
                )
                continue

            messages_data = vk_session.method(
                'messages.getById',
                {'message_ids': set([event.message_id,])}
            )
            pprint(messages_data)
            messages_data = messages_data['items'][0]

            links = get_photos_links(messages_data)
            print(links)
            print("len = ", len(links))

            if(len(links) == 0):
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

            for c, plink in enumerate(links):
                print(c)
                with urllib.request.urlopen(plink) as response, open(os.path.join('data', muid, str(c) + '.jpg'), 'wb') as out_file:
                    data = response.read() # a `bytes` object
                    out_file.write(data)

            zip_name = os.path.join('data', str(muid) + ".zip")
            zipf = zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED)
            zipdir(pics_path, zipf)
            zipf.close()

            doc = upload.document_message(doc=zip_name, title=event.text + str(muid) + ".zip", peer_id=event.peer_id)
            doc = doc['doc']
            pprint(doc)
            vk.messages.send(
                user_id=event.user_id,
                attachment='doc{}_{}'.format(doc['owner_id'], doc['id']),
                random_id=get_random_id(),
                message='Ok. Done.'
            )

            print('ok')


def get_photos_links(msg):
    print("in get_photos_links")
    res = []
    pprint(msg)
    for a in msg['attachments']:
        print("in get_photos_links attachemts")
        if('photo' in a):
#            pprint([ s['url'] for s in a['photo']['sizes'] if s['type'] == 'z'])
            s = sorted(a['photo']['sizes'], key=lambda x: x['width'])
            pprint(s)
            res.append(s[-1]['url'])
            pprint(res)
    if 'reply_message' in msg:
        print("in get_photos_links reply")
        messages_data = vk_session.method(
            'messages.getById',
            {'message_ids': set([ msg['reply_message']['id'] ])}
        )
        pprint(messages_data)
        messages_data = messages_data['items'][0]
        res.extend(get_photos_links(messages_data))
    if 'fwd_messages' in msg:
        print("in get_photos_links fwd")
        for m in msg['fwd_messages']:
            res.extend(get_photos_links(m))
    return res



if __name__ == '__main__':
    main()
