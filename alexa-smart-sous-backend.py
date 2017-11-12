
import requests
import boto3
import json

# -------------- Helpers to make Alexa and speech work -------------------------

def humanize_measurement(measurement):

    measureMap = {
        "oz" : "ounces",
        "lb" : "pound",
        "Tbsp" : "table spoon",
        "tsp" : "tea spoon",
        "Tbsps" : "table spoons",
        "tsps" : "tea spoons",
        "oz" : "ounces"
        }

    if measurement in measureMap:
        return measureMap[measurement]
    else:
        return measurement
    

def familiarize_recipe_name(recipe_name):
    output = recipe_name.lower().replace('&', 'and').replace(',', '').replace('-', " ")
    return output

# --------------- Helpers that build all of the responses ----------------------

def build_speechlet_response(title, output, reprompt_text, should_end_session):
    return {
        'outputSpeech': {
            'type': 'PlainText',
            'text': output
        },
        'card': {
            'type': 'Simple',
            'title': "SessionSpeechlet - " + title,
            'content': "SessionSpeechlet - " + output
        },
        'reprompt': {
            'outputSpeech': {
                'type': 'PlainText',
                'text': reprompt_text
            }
        },
        'shouldEndSession': should_end_session
    }


def build_response(session_attributes, speechlet_response):
    return {
        'version': '1.0',
        'sessionAttributes': session_attributes,
        'response': speechlet_response
    }


# --------------- Functions that control the skill's behavior ------------------
    
def get_user_id(session):
    return session['user']['userId'].replace('amzn1.ask.account.','')


def save_state(session, recipe_id, current_step):
    #only save if we have a loaded recipe
    userID = get_user_id(session)
    s3 = boto3.resource('s3')

    #generate save state data from current recipe
    data = {}
    data['recipe_id'] = recipe_id
    data['current_step'] = current_step

    #create a file for writing to
    f = open('/tmp/tempfile', 'w')

    #write json to file
    json.dump(data, f)
    f.close()
    f = open('/tmp/tempfile', 'rb')

    #upload file to s3
    s3.Bucket('smartsous').put_object(Key=userID, Body=f)

    #cleanup
    f.close()
    return True

#returns user data if it exists, or false if there is no data
def load_state(session):
    user_id = get_user_id(session)
    s3 = boto3.resource('s3')
    try:
        data = json.loads(s3.Object('smartsous', user_id).get()['Body'].read().decode('utf8'))
    except:
        return False
    return data

def get_welcome_response():
    """ If we wanted to initialize the session to have some attributes we could
    add those here
    """

    session_attributes = {}
    card_title = "Welcome"
    speech_output = "Welcome to Smart Sous chef!" \
                    "you can search for recipes, "\
                    "or start cooking right away" \
    # If the user either does not reply to the welcome message or says something
    # that is not understood, they will be prompted again with this text.
    reprompt_text = "You can start a recipe by saying, " \
                    "let's make Mushroom & Swiss Burgers with Pan-Seared Fingerling Potatoes"
    should_end_session = False
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


def handle_session_end_request():
    speech_output = "Thank you for using smart sous chef!" \
                    "Enjoy your meal!"
    # Setting this to true ends the session and exits the skill.
    should_end_session = True
    return build_response({}, build_speechlet_response(
        card_title, speech_output, None, should_end_session))

def create_active_recipe_from_id(recipe_id):
    session_attributes = {}
    session_attributes = requests.get('http://sous.matthewpdias.com/recipes/{}.json'.format(recipe_id)).json()
    session_attributes['current_step'] = 0

    return session_attributes


def create_active_recipe_attributes(recipe_name):

    r = requests.get('http://sous.matthewpdias.com/recipes.json')

    #oh my god, its Jason Bourne
    json_bourne = r.json()

    recipe_id = 0

    for recipe in json_bourne['recipes']:
        if familiarize_recipe_name(recipe['name']) == recipe_name:
            recipe_id = (recipe['id'])
            break

    if recipe_id == 0:
        print('NO RECIPE NAMED: {} WAS FOUND'.format(recipe_name))
    #TODO: error check if the recipe_id is bad

    session_attributes = requests.get('http://sous.matthewpdias.com/recipes/{}.json'.format(recipe_id)).json()
    session_attributes['current_step'] = 0
    return session_attributes


def create_search_response(keyword):
    response = []
    json = requests.get('http://sous.matthewpdias.com/search/{}.json'.format(keyword)).json()
    for recipe in json['search_results']:
        response.append(recipe)
    return response

def get_search_response(intent, session):
    session_attributes = {}
    card_title = intent['name']
    should_end_session = False

    if 'keyword' in intent['slots']:
        keyword = intent['slots']['keyword']['value']
        search_response = create_search_response(keyword)

        session_attributes['search_results'] = search_response

        if len(search_response) > 2:
            speech_output = "Here are some recipes found searching for " + keyword + "; " \
            + "recipe 1, " + search_response[0]['name'] + ". recipe 2, " + search_response[1]['name'] + ". recipe 3, " +  search_response[2]['name']
            reprompt_text = "search again or say, select result 3 to choose" + search_response[0]['name']
        elif len(search_response) > 1:
            speech_output = "Here are some recipes found searching for " + keyword + "; " \
            + "recipe 1, " + search_response[0]['name'] + ". Rr recipe 2, " + search_response[1]['name']
            reprompt_text = "search again or say, select result 2 to choose " + search_response[0]['name']
        elif len(search_response) > 0:
            speech_output = "Here is a recipe found searching for " + keyword + "; " \
            + search_response[0]['name']
            reprompt_text = "search again or say, select result 1 to choose " + search_response[0]['name']
        else:
            speech_output = "No recipes found searching for " + keyword
            reprompt_text = "search again with a different keyword"
                        
    else:
        speech_output = "intent slot was empty... recipe was misheard or not in the enum."

        reprompt_text = "You can search recipe by saying, \n search for Potatoes"

    return build_response(session_attributes, build_speechlet_response(card_title, speech_output, reprompt_text, should_end_session))


def select_search_result(intent, session):
    card_title = intent['name']
    session_attributes = session['attributes']
    should_end_session = False

    #if we don't have results
    if "search_results" not in session.get('attributes', {}):
        speech_output = "No search results to select from, try searching first"
        reprompt_text = "search by saying, search for potatoes"

    #if we don't have a selection
    elif 'selection' not in intent['slots']:
        speech_output = "no numeric selection detected, please try again" 
        reprompt_text = "select a search result by saying, select number 1"

    #if the selection is too high
    elif len(session_attributes['search_results']) < int(intent['slots']['selection']['value']):
        speech_output = "selection too high, only " + str(len(session_attributes['search_results'])) + " options to choose from."
        reprompt_text = "select a search result by saying, select number 1"

    #if selection is too low
    elif int(intent['slots']['selection']['value']) < 1:
        speech_output = "selection detected as too low, did you try zero?"
        reprompt_text = "select a search result by saying, select number 1"

    #selection is within reason and we have results to choose from
    else:
        selection = (int(intent['slots']['selection']['value']) - 1)
        active_recipe = session_attributes['search_results'][selection]['name']
        active_recipe_id = session_attributes['search_results'][selection]['id']

        session_attributes = create_active_recipe_from_id(active_recipe_id)

        speech_output = "let's get started making " + active_recipe + ".\n Ask me what ingredients you need."                
        reprompt_text = "ask me, \n what ingredients do I need?"

    return build_response(session_attributes, build_speechlet_response(card_title, speech_output, reprompt_text, should_end_session))


def set_recipe_in_session(intent, session):
    card_title = intent['name']
    session_attributes = {}
    should_end_session = False
    
    if 'recipe' in intent['slots']:
        active_recipe = intent['slots']['recipe']['value']
        session_attributes = create_active_recipe_attributes(active_recipe)
        save_state(session, session_attributes['id'], session_attributes['current_step'])

        speech_output = "let's get started making " + active_recipe + ".\n Ask me what ingredients you need."
                        
        reprompt_text = "ask me, \n what ingredients do I need?"
    else:
        speech_output = "intent slot was empty... recipe was misheard or not in the enum."

        reprompt_text = "You can start a recipe by saying, \n let's make Mushroom & Swiss Burgers with Pan-Seared Fingerling Potatoes"

    return build_response(session_attributes, build_speechlet_response(card_title, speech_output, reprompt_text, should_end_session))


def get_ingredients_in_session(intent, session):
    session_attributes = {}
    card_title = intent['name']
    should_end_session = False

    speech_output = ""

    if "ingredients" in session.get('attributes', {}):
        ingredients = session['attributes']['ingredients']
        session_attributes = session['attributes']

        for ingredient in session['attributes']['ingredients']:
            speech_output += humanize_measurement(ingredient['amount']) + ingredient['name'] + ",\n"

        reprompt_text = "You can ask for the ingredients again, or say 'move on' to continue"
    else:

        speech_output = "No recipe selected, \n  Select a recipe by saying: \nlet's make Mushroom & Swiss Burgers with Pan-Seared Fingerling Potatoes"

        reprompt_text = "You can start a recipe by saying, \n let's make Mushroom & Swiss Burgers with Pan-Seared Fingerling Potatoes"

    return build_response(session_attributes, build_speechlet_response(intent['name'], speech_output, reprompt_text, should_end_session))


def get_current_step_response(intent, session):
    session_attributes = {}
    card_title = intent['name']
    should_end_session = False

    if "step" in session.get('attributes', {}):
        steps = session['attributes']['step']
        session_attributes = session['attributes']
        save_state(session, session_attributes['id'], session_attributes['current_step'])

        speech_output = steps[session['attributes']['current_step']]['instructions']

        reprompt_text = "you can say, 'go back', 'repeat the step', or 'move on' to keep cooking!"

    else:
        speech_output = "No recipe selected, \n  Select a recipe by saying: \nlet's make Mushroom & Swiss Burgers with Pan-Seared Fingerling Potatoes"

        reprompt_text = "You can start a recipe by saying, \n let's make Mushroom & Swiss Burgers with Pan-Seared Fingerling Potatoes"

    return build_response(session_attributes, build_speechlet_response(intent['name'], speech_output, reprompt_text, should_end_session))


def get_previous_step_response(intent, session):

    if "current_step" in session.get('attributes', {}):
            if session['attributes']['current_step'] != 0:
                session['attributes']['current_step'] -= 1

            return get_current_step_response(intent, session)

    #using get_ingredients as error checking
    else:
            print("NO CURRENT STEP DETECTED!")
            return get_ingredients_in_session(intent, session)


def get_next_step_response(intent, session):

    if "current_step" in session['attributes']:
            if session['attributes']['current_step'] < len(session['attributes']['step']):
                session['attributes']['current_step'] += 1
            return get_current_step_response(intent, session)
    #using get_ingredients as error checking
    else:
            print("NO CURRENT STEP DETECTED!")
            return get_ingredients_in_session(intent, session)      
    

# --------------- Events ------------------

def on_session_started(session_started_request, session):
    """ Called when the session starts """

    #print("on_session_started requestId=" + session_started_request['requestId'] + ", sessionId=" + session['sessionId'])


def on_launch(launch_request, session):
    """ Called when the user launches the skill without specifying what they
    want
    """

    #print("on_launch requestId=" + launch_request['requestId'] + ", sessionId=" + session['sessionId'])
    # Dispatch to your skill's launch
    return get_welcome_response()


def on_intent(intent_request, session):
    """ Called when the user specifies an intent for this skill """

    #print("on_intent requestId=" + intent_request['requestId'] + ", sessionId=" + session['sessionId'])

    intent = intent_request['intent']
    intent_name = intent_request['intent']['name']

    # Dispatch to your skill's intent handlers
    if intent_name == "SelectRecipeIntent":
        return set_recipe_in_session(intent, session)
    if intent_name == "GetIngredientsIntent":
            return get_ingredients_in_session(intent, session)
    elif intent_name == "PreviousStepIntent":
        return get_previous_step_response(intent, session)
    elif intent_name == "RepeatStepIntent":
        return get_current_step_response(intent, session)
    elif intent_name == "NextStepIntent":
        return get_next_step_response(intent, session)
    elif intent_name == "SearchRecipesIntent":
        return get_search_response(intent, session)
    elif intent_name == "SelectSearchResultIntent":
        return select_search_result(intent, session)
    elif intent_name == "AMAZON.HelpIntent":
        return get_welcome_response(intent, session)
    elif intent_name == "AMAZON.CancelIntent" or intent_name == "AMAZON.StopIntent":

        return handle_session_end_request(intent, session)
    else:
        raise ValueError("Invalid intent")


def on_session_ended(session_ended_request, session):
    """ Called when the user ends the session.

    Is not called when the skill returns should_end_session=true
    """
    #print("on_session_ended requestId=" + session_ended_request['requestId'] + ", sessionId=" + session['sessionId'])
    # add cleanup logic here


# --------------- Main handler ------------------

def lambda_handler(event, context):
    """ Route the incoming request based on type (LaunchRequest, IntentRequest,
    etc.) The JSON body of the request is provided in the event parameter.
    """
    #print("event.session.application.applicationId=" + event['session']['application']['applicationId'])

    """
    Uncomment this if statement and populate with your skill's application ID to
    prevent someone else from configuring a skill that sends requests to this
    function.
    """
    # if (event['session']['application']['applicationId'] !=
    #         "amzn1.echo-sdk-ams.app.[unique-value-here]"):
    #     raise ValueError("Invalid Application ID")

    if event['session']['new']:
        on_session_started({'requestId': event['request']['requestId']},
                           event['session'])

    if event['request']['type'] == "LaunchRequest":
        return on_launch(event['request'], event['session'])
    elif event['request']['type'] == "IntentRequest":
        return on_intent(event['request'], event['session'])
    elif event['request']['type'] == "SessionEndedRequest":
        return on_session_ended(event['request'], event['session'])