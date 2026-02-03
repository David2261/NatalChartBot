user_states = {}

def get_state(uid):
	return user_states.get(uid, {}).get('state', 'START')

def set_state(uid, state, data=None):
	if uid not in user_states:
		user_states[uid] = {'state': state, 'data': {}, 'paid': False}
	user_states[uid]['state'] = state
	if data:
		user_states[uid]['data'].update(data)

def get_data(uid):
	return user_states.get(uid, {}).get('data', {})

def is_paid(uid):
	return user_states.get(uid, {}).get('paid', False)

def set_paid(uid, charge_id):
	if uid in user_states:
		user_states[uid]['paid'] = True
