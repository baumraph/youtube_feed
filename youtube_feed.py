import urllib.request
import json
import argparse
import pickle
import os.path
import dateutil.parser
import webbrowser
import urwid

API_KEY = 'ENTER_YOUR_API_KEY'				# Api key (there are public ones, so you do not have to create one)
DATETIME_FORMAT = '%d.%m.%Y %H:%M'			# Format for date and time
MAX_RESULTS = 5						# Maximum number of videos in the feed per channel
subscriptions = []
already_watched = []

class Subscription:
	def __init__(self, channel_id, channel_title, playlist_id):
		self.channel_id = channel_id
		self.channel_title = channel_title
		self.playlist_id = playlist_id

class Video:
	def __init__(self, channel_title, video_id, video_title, published_at):
		self.channel_title = channel_title
		self.video_id = video_id
		self.video_title = video_title
		self.published_at = published_at

def save_already_watched():
	with open('already_watched', 'wb') as f:
		pickle.dump(already_watched, f)

def load_already_watched():
	global already_watched
	if os.path.exists("already_watched"):
		with open('already_watched', 'rb') as f:
			already_watched = pickle.load(f)

def save_subscriptions():
	with open('subscriptions', 'wb') as f:
		pickle.dump(subscriptions, f)

def load_subscriptions():
	global subscriptions
	if os.path.exists("subscriptions"):
		with open('subscriptions', 'rb') as f:
			subscriptions = pickle.load(f)

def send_request(url):
	url = url + "&key=" + API_KEY
	request = urllib.request.urlopen(url)
	if request.getcode() != 200:
		return None
	charset = request.info().get_content_charset()
	content = request.read().decode(charset)
	response = json.loads(content)
	return response

def get_channel_id(channel_name):
	url = 'https://www.googleapis.com/youtube/v3/search?part=id&type=channel&q={}'.format(urllib.request.quote(channel_name))
	response = send_request(url)
	if response == None:
		return None
	if len(response['items']) == 0:
		return None
	channel_id = response['items'][0]['id']['channelId']
	return channel_id

def get_channel_title(channel_id):
	url = 'https://www.googleapis.com/youtube/v3/channels?part=snippet&id={}'.format(urllib.request.quote(channel_id))
	response = send_request(url)
	if response == None:
		return None
	if len(response['items']) == 0:
		return None
	channel_title = response['items'][0]['snippet']['title']
	return channel_title

def list_subscriptions():
	text = 'Subscriptions (total of {}):'.format(len(subscriptions))
	print(text)
	print('=' * len(text))
	for subscription in subscriptions:
		print(subscription.channel_title)

def get_playlist_id(channel_id):
	url = 'https://www.googleapis.com/youtube/v3/channels?part=contentDetails&order=date&id={}'.format(urllib.request.quote(channel_id))
	response = send_request(url)
	if response == None:
		return None
	if len(response['items']) == 0:
		return None
	playlist_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
	return playlist_id

def add_channel(channel_username):
	channel_id = get_channel_id(channel_username)
	if channel_id == None:
		print('Could not find a channel with the username "{}"'.format(channel_username ))
		return

	# Check if channel is already in the subscription list
	for subscription in subscriptions:
		if subscription.channel_id == channel_id:
			print('The channel "{}" is already in your subscription list'.format(subscription.channel_title))
			return
	
	# Get more information about the chanenl
	channel_title = get_channel_title(channel_id)
	playlist_id = get_playlist_id(channel_id)

	# Add new subscription
	subscription = Subscription(channel_id, channel_title, playlist_id)
	subscriptions.append(subscription)
	save_subscriptions()
	print('Added channel "{}" to your subscription list'.format(channel_title))

def remove_channel(channel_title):
	channel_title = str.lower(channel_title)
	for subscription in subscriptions:
		if channel_title in str.lower(subscription.channel_title):
			channel_title = subscription.channel_title
			subscriptions.remove(subscription)
			save_subscriptions()
			print('Removed channel "{}" from your subscription list'.format(channel_title))
			return
	print('Could not find a channel with the title "{}"'.format(channel_title))

def get_latest_videos(playlist_id, max_results=10):
	url = 'https://www.googleapis.com/youtube/v3/playlistItems?part=snippet,contentDetails&maxResults={}&order=date&playlistId={}'.format(max_results, playlist_id)
	response = send_request(url)
	if response == None:
		return None
	if len(response['items']) == 0:
		return None
	videos = []
	for item in response['items']:
		channel_title = item['snippet']['channelTitle']
		video_id = item['contentDetails']['videoId']
		video_title = item['snippet']['title']
		published_at = dateutil.parser.parse(item['snippet']['publishedAt'])
		video = Video(channel_title, video_id, video_title, published_at)
		videos.append(video)
	return videos

def play_video(button, video_id):
	# Add to already_watched list
	if video_id not in already_watched:
		already_watched.append(video_id)
		save_already_watched()
		button.set_label('')
	url = 'https://www.youtube.com/watch?v={}'.format(video_id)
	webbrowser.open(url)

# Feed
def menu():
	body = [urwid.Text('Youtube Feed'), urwid.Divider()]
	
	# Get for each subscriptions the latest 10 videos
	videos = []
	for subscription in subscriptions:
		videos.extend(get_latest_videos(subscription.playlist_id, MAX_RESULTS))

	# Sort the video by date
	videos = sorted(videos, key=lambda video: video.published_at, reverse=True)
	
	# Print a maximum of 50 videos
	for video in videos:
		button_text = ''
		if video.video_id not in already_watched:
			button_text = ' [NEW]'

		widgets = []
		widgets.append(urwid.Divider())
		widgets.append(urwid.Text(video.video_title, align='left'))
		widgets.append(urwid.Text(video.channel_title, align='right'))
		widgets.append(urwid.Button(button_text, play_video, video.video_id))
		
		pile = urwid.Padding(urwid.Pile(widgets), left=1, right=1)
		pile = urwid.AttrMap(urwid.LineBox(pile, title=video.published_at.strftime(DATETIME_FORMAT)), None, focus_map='reversed')

		body.append(pile)
	return urwid.ListBox(urwid.SimpleFocusListWalker(body))

def handle_input(key):
    if key in ('esc', 'q', 'Q'):
        raise urwid.ExitMainLoop()

def show_feed():
	print('Loading feed (this can take some time)')
	main = urwid.Padding(menu(), left=1, right=1)
	urwid.MainLoop(main, palette=[('reversed', 'standout', '')], unhandled_input=handle_input).run()

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='Manage your Youtube feed without an account')
	parser.add_argument('-l', help='List all channels in your subscription list', nargs='?', default='off')
	parser.add_argument('-s', help='Show your personal Youtube feed', nargs='?', default='off')
	parser.add_argument('-a', help='Add a channel to your subcription list')
	parser.add_argument('-r', help='Remove a channel from your subscription list')
	args = parser.parse_args()

	load_subscriptions()
	load_already_watched()

	if args.l == None:
		list_subscriptions()
	if args.s == None:
		show_feed()
	if args.a:
		add_channel(args.a)
	if args.r:
		remove_channel(args.r)
