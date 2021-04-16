import pymongo
import sys, getopt
from datetime import datetime, timedelta
import math
import concurrent.futures

# Specify the MongoDB server (default address is mongodb://localhost:27017/)
mongo_client = pymongo.MongoClient("mongodb://localhost:27017/")

# Specify the name of database
mongo_db = mongo_client["MCS"]

# Getting all the collections required from the MongoDB1
user_profiles = mongo_db['user_profiles_v3']
readmes_gensim = mongo_db['readmes_v2_tfidf_gensim']
users = mongo_db['users']
watching = mongo_db['watching']

# The ID's of all users in the study in a list
ALL_USERS = users.find({}, {"_id":0, "id":1}).distinct("id")

# Default number of recommendations given
# Can be changed here or specified with -n <number> in the command line
DEFAULT_NUM_RECOMMENDATIONS = 10

def relevance(user, number_of_recommendations=DEFAULT_NUM_RECOMMENDATIONS):
    """
    Calculate the relevance score of a specific user. Takes all 'watched' repositories from the user and calculates the
    relevance from the overall set against each of these.
    :param user: ID of the user in question
    :param number_of_recommendations: Default to DEFAULT_NUM_RECOMMENDATIONS or takes in an int to modify
    :return: list of recommendations sorted by recommendation value in a list of tuples, EX: [(<Github Repo ID>, <Recommendation level>)]
    """
    repoQ = readmes_gensim.find({'watchers': {'$elemMatch': {'user_id': user}}}, {"_id":0, "id":1, "readme_tfidf":1, "watchers":1})
    suggestion = []
    # For each of the repositories watched by the 'user'
    for x in repoQ:
        # NOTE: This set only returns repositories that at minimum one (1) user in the study has followed
        cursor = readmes_gensim.find({'watchers': {'$elemMatch': {'user_id': {'$in': ALL_USERS}}}}, {"_id": 0, "id": 1, "readme_tfidf": 1, "watchers": 1}, no_cursor_timeout=True)
        # For each of the repoisitories in the overall set
        for y in cursor:
            with concurrent.futures.ThreadPoolExecutor(3) as executor:
                try:
                    # Readme Relevance Score
                    c1 = executor.submit(compute_readme_relevance, x, y)

                    # Time Relevance Score
                    c2 = executor.submit(compute_time_relevance, x, y)

                    # Stargazer Score
                    c3 = executor.submit(compute_stargazer_user_relevance, x, y)

                    # Multiply the results together and append to the suggestion list
                    relevance = c1.result() * c2.result() * c3.result()
                    suggestion.append((y['id'], relevance))
                    # Sort by relevance score in each tuple
                    suggestion.sort(key = lambda x: (x[1]), reverse=True)
                    # Keep number of suggestion below the number of recommendations threshold.
                    # Kicks out the lowest recommendation scores
                    while len(suggestion) > number_of_recommendations:
                        suggestion.pop()
                except:
                    # Could not calculate the score of that repository
                    suggestion.append("Error")
        # Cursor needs to be closed or else will leak
        cursor.close()
    return suggestion


def compute_readme_relevance(first_repo, second_repo):
    """
    Calculate the Readme Relevance score by taking the cosine similarity between the read me files of the first and second repo
    :param first_repo: One of the repositories that the user is watching
    :param second_repo: One of the repositories in the overall set
    :return: relevance score, int
    """
    # Make sure the readme's are not empty
    try:
        if first_repo['readme_tfidf']['nan'] == 1:
            return 0
        if second_repo['readme_tfidf']['nan'] == 1:
            return 0
    except:
        top = 0
        # Intersection of TFIDF scores between both repositories
        inter = intersection([x for x in first_repo['readme_tfidf']], [x for x in second_repo['readme_tfidf']])

        # No intersection : Return 0
        if len(inter) == 0:
            return 0

        # For each word in the intersection, multiply the scores together
        for x in inter:
            if first_repo['readme_tfidf'][x] and second_repo['readme_tfidf'][x]:
                top += (first_repo['readme_tfidf'][x] * second_repo['readme_tfidf'][x])
            else:
                continue

        if round(top) == 0:
            return 0

        # Calculate the denominator of the equation outlined in Repopal Paper
        f = 0
        s = 0
        for x in first_repo['readme_tfidf']:
            f += (first_repo['readme_tfidf'][x] ** 2)
        for x in second_repo['readme_tfidf']:
            s += (second_repo['readme_tfidf'][x] ** 2)
        bottom = math.sqrt(f) * math.sqrt(s)
        if bottom == 0:
            return 0
        return top / bottom

def compute_stargazer_user_relevance(first_repo, second_repo):
    """
    Calculate the Stargazer relevance score between two repositories
    :param first_repo: One of the repositories that the user is watching
    :param second_repo: One of the repositories in the overall set
    :return: relevance score, int
    """
    repo_one = []
    repo_two = []

    # Get all users watching the first repo that is in the study
    for x in first_repo['watchers']:
        if x['user_id'] in ALL_USERS:
            repo_one.append(x['user_id'])
    # Get all users watching the second repo that is in the study
    for x in second_repo['watchers']:
        if x['user_id'] in ALL_USERS:
            repo_two.append(x['user_id'])

    if repo_one == repo_two:
        return 0
    if len(repo_one) == 0 or len(repo_two) == 0:
        return 0

    # Compute the similarity score between two users
    total = 0
    for x in repo_one:
        for y in repo_two:
            total += compute_sim(x, y)

    if len(repo_one + repo_two) == 0:
        return 0
    if total / len(repo_one+repo_two) == 0:
        return 0

    return total / len(repo_one + repo_two)

def compute_sim(user1, user2):
    """
    Calculate the similarity score between two users from the recalculated score in the database
    :param user1: ID of a user
    :param user2: ID of a user
    :return: similarity score, int
    """

    #Get both users from the database as per their user ID
    user_one = user_profiles.find_one({"user_id": user1}, {"_id": 0, "watching": 1})
    user_two = user_profiles.find_one({"user_id": user2}, {"_id": 0, "watching": 1})
    if user_one == None or user_two == None:
        return 0

    # Make sure they are watching a repository
    if not user_one['watching'] or not user_two['watching']:
        return 0

    # Intersection of the watching list
    inter = intersection(user_one['watching'], user_two['watching'])
    # Union of the watching list
    uni = union(user_one['watching'], user_two['watching'])

    if len(uni) == 0:
        return 0
    return len(inter) / len(uni)

def compute_time_relevance(first_repo, second_repo):
    """
    Calculate the time relevance score between two repositories
    :param first_repo: One of the repositories that the user is watching
    :param second_repo: One of the repositories in the overall set
    :return: relevance score, int
    """

    # Get all the users that are watching both repositories respectively
    repo_one = first_repo['watchers']
    repo_two = second_repo['watchers']

    if not repo_one or not repo_two:
        return 0
    if repo_one == repo_two:
        return 0

    # Get the intersection of these repository watch lists
    inter = intersection_on_user(repo_one, repo_two)
    if not inter:
        return 0

    total = 0
    sum = 0
    dates = []

    # For every user that watches both repositories
    for each in inter:
        total += 1
        # For every user in the first repository
        for x in repo_one:
            # For every user in the second repository
            for y in repo_two:
                # Calculate the difference in time that one user in the intersection watched both repos
                if x['user_id'] == each and y['user_id'] == each:
                    date_one = datetime.strptime(y['created_at'], "%Y/%m/%d %H:%M:%S")
                    date_two = datetime.strptime(x['created_at'], "%Y/%m/%d %H:%M:%S")

                    # Round to roughly the nearest hour
                    bot = abs((date_two - date_one).seconds/3600)
                    if bot == 0:
                        sum += 1
                    else:
                        sum += (1 / bot)
    average = sum / total
    if average == 0:
        return 0
    return average

def intersection_on_user(l1, l2):
    """
    Helper function that gets the intersection of user IDs only between two outputs from the database
    :param l1: Watchlist of users from a repository
    :param l2: Watchlist of users from a repository
    :return: Intersection of those users
    """
    nL1 = [x['user_id'] for x in l1]
    nL2 = [x['user_id'] for x in l2]
    return intersection(nL1, nL2)

def intersection(l1,l2):
    """
    Intersection of two lists
    :param l1: List
    :param l2: List
    :return: All users that are in both lists
    """
    lst3 = [value for value in l1 if value in l2]
    return lst3

def union(l1, l2):
    """
    Union of two lists
    :param l1: List
    :param l2: List
    :return: All users from both lists
    """
    l3 = l1 + l2
    return l3

if __name__ == "__main__":
    argv = sys.argv[1:]
    user = 0
    num = 0
    try:
        opts, args = getopt.getopt(argv, "ahu:n:", ["all","help","user=","num="])
    except getopt.GetoptError:
        print("main.py -u <user id> [optional] -n <numberOfRecommendations>")
        print("main.py -a/--all users, this will run through all users in the study from the collection 'users'")
        sys.exit(2)
    for opt, arg in opts:
        if opt in ('-h', "--help"):
            print("main.py -u <user id> [optional] -n <numberOfRecommendations>")
            print("main.py -a/--all users, this will run through all users in the study from the collection 'users'")
            print(f'Default number of recommendations is {DEFAULT_NUM_RECOMMENDATIONS}')
            sys.exit()
        elif opt in ("-u", "--user"):
            user = int(arg)
        elif opt in ("-n", "--num"):
            num = int(arg)
        elif opt in ("-a", "--all"):
            f = open(f'output.txt', "w")
            for each in ALL_USERS:
                print(f'Processing {each}...')
                f.write(str(each) + " ")
                f.write(str(relevance(each, 10)) + "\n")
            f.close()
            print(f'Your output file is output.txt and contains all the recommendations for the user')
            break
    # If no number paramter is provided, run on user with default number of recommendations
    if num == 0:
        print(f'Running relevance of user {user} with {DEFAULT_NUM_RECOMMENDATIONS} recommendations...')
        ret = relevance(user)
        if len(ret) == 0:
            print(f'Could not find suggestions for {user}. This could be because the dataset of repositories do not include some/all of the repository that user follows.')
        else:
            f = open(f'output_{user}.txt', "w")
            f.write(str(user) + " ")
            f.write(str(ret) + "\n")
            f.close()
    # If no user specified AND no -a/--all option specified
    if user == 0:
        print("User is not optional")
        print("main.py -u <user id> [optional] -n <numberOfRecommendations>")
        print("main.py -a/--all users, this will run through all users in the study from the collection 'users'")
    # If both number and user is specified
    if num != 0 and user != 0:
        print(f'Running relevance of user {user} with {num} recommendations...')
        ret = relevance(user, num)
        if len(ret) == 0:
            print(f'Could not find suggestions for user: {user}. This could be because the dataset of repositories do not include some/all of the repository that user follows.')
        else:
            # New file per person ran
            f = open(f'output_{user}.txt', "w")
            f.write(str(user) + " ")
            f.write(str(ret) + "\n")
            f.close()
