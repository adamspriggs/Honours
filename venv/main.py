# pymongo is the Python plugin used to connect to MongoDB server.
# You need to install it via command-line tool first.
import pymongo
import sys, getopt
from datetime import datetime, timedelta
import math
import concurrent.futures

# Specify the MongoDB server (default address is mongodb://localhost:27017/)
mongo_client = pymongo.MongoClient("mongodb://localhost:27017/")

# Specify the name of database
mongo_db = mongo_client["MCS"]

user_profiles = mongo_db['user_profiles_v3']
readmes_gensim = mongo_db['readmes_v2_tfidf_gensim']
users = mongo_db['users']

DEFAULT_NUM_RECOMMENDATIONS = 10

#98036093
def relevance(user, number_of_recommendations=DEFAULT_NUM_RECOMMENDATIONS):
    # TEST Repo Set
    # Test ONE repo first
    repoQ = [readmes_gensim.find_one({"id": user}, {"_id": 0, "id": 1, "readme_tfidf":1, "watchers":1})]
    repo_set = readmes_gensim.find({}, {"_id" : 0})
    suggestion = []
    counter = 0

    # Repo's to test again
    for x in repoQ:
        for y in repo_set:
            counter += 1
            if counter % 85000 == 0:
                print(f'{round(counter/1700000)}% complete')
            with concurrent.futures.ThreadPoolExecutor() as executor:
                c1 = executor.submit(compute_readme_relevance, x, y)
                c2 = executor.submit(compute_time_relevance, x, y)
                c3 = executor.submit(compute_stargazer_user_relevance, x, y)

                relevance = c1.result() * c2.result() * c3.result()
                suggestion.append((y['id'], relevance))
                suggestion.sort(key = lambda x: (x[1]), reverse=True)
                while len(suggestion) > number_of_recommendations:
                    suggestion.pop()

    return suggestion


def compute_readme_relevance(first_repo, second_repo):
    top = 0
    inter = intersection([x for x in first_repo['readme_tfidf']], [x for x in second_repo['readme_tfidf']])

    for x in inter:
        if first_repo['readme_tfidf'][x] and second_repo['readme_tfidf'][x]:
            top += (first_repo['readme_tfidf'][x] * second_repo['readme_tfidf'][x])
        else:
            continue

    f = 0
    s = 0
    for x in first_repo['readme_tfidf']:
        f += (first_repo['readme_tfidf'][x] ** 2)
    for x in second_repo['readme_tfidf']:
        s += (second_repo['readme_tfidf'][x] ** 2)
    bottom = math.sqrt(f) ** math.sqrt(s)
    return top / bottom

def compute_stargazer_user_relevance(first_repo, second_repo):
    repo_one = [x['user_id'] for x in first_repo['watchers']]
    repo_two = [x['user_id'] for x in second_repo['watchers']]

    if repo_one == repo_two:
        return 0
    if len(repo_one) == 0 or len(repo_two) == 0:
        return 0

    total = 0
    for x in repo_one:
        for y in repo_two:
            total += compute_sim(x, y)

    #Print relevance
    if len(repo_one + repo_two) == 0:
        return 0
    return total / len(repo_one + repo_two)

def compute_sim(user1, user2):
    user_one = user_profiles.find_one({"user_id": user1}, {"_id": 0, "watching": 1})
    user_two = user_profiles.find_one({"user_id": user2}, {"_id": 0, "watching": 1})
    if user_one == None or user_two == None:
        return 0

    if not user_one['watching'] or not user_two['watching']:
        return 0

    inter = intersection(user_one['watching'], user_two['watching'])
    uni = union(user_one['watching'], user_two['watching'])

    if len(uni) == 0:
        return 0;
    return len(inter) / len(uni)

def compute_time_relevance(first_repo, second_repo):
    repo_one = first_repo['watchers']
    repo_two = second_repo['watchers']
    if not repo_one or not repo_two:
        return 0
    if repo_one == repo_two:
        return 0

    inter = intersection_on_user(repo_one, repo_two)
    if not inter:
        return 0

    total = 0
    sum = 0
    dates = []

    for each in inter:
        total += 1
        for x in repo_one:
            for y in repo_two:
                if x['user_id'] == each and y['user_id'] == each:
                    date_one = datetime.strptime(y['created_at'], "%Y/%m/%d %H:%M:%S")
                    date_two = datetime.strptime(x['created_at'], "%Y/%m/%d %H:%M:%S")
                    bot = abs((date_two - date_one).seconds/3600)
                    if bot == 0:
                        sum += 1
                    else:
                        sum += (1 / bot)


    average = sum / total
    return average

def intersection_on_user(l1, l2):
    nL1 = [x['user_id'] for x in l1]
    nL2 = [x['user_id'] for x in l2]
    return intersection(nL1, nL2)

def intersection(l1,l2):
    lst3 = [value for value in l1 if value in l2]
    return lst3

def union(l1, l2):
    l3 = l1 + l2
    return l3

if __name__ == "__main__":
    argv = sys.argv[1:]
    user = 0
    num = 0
    try:
        opts, args = getopt.getopt(argv, "h:u:n:", ["user=","num=","help="])
    except getopt.GetoptError:
        print("main.py -u <user id> [optional] -n <numberOfRecommendations>")
        sys.exit(2)
    for opt, arg in opts:
        if opt in ('-h', "--help"):
            print("main.py -u <user id> [optional] -n <numberOfRecommendations>")
            print(f'Default number of recommendations is {DEFAULT_NUM_RECOMMENDATIONS}')
            sys.exit()
        elif opt in ("-u", "--user"):
            user = int(arg)
        elif opt in ("-n", "--num"):
            num = int(arg)
    if num == 0:
        print(f'Running relevance of user {user} with {DEFAULT_NUM_RECOMMENDATIONS} recommendations')
        print(relevance(user))
    if user == 0:
        print("User is not optional")
        print("main.py -u <user id> [optional] -n <numberOfRecommendations>")
    if num != 0 and user != 0:
        print(f'Running relevance of user {user} with {num} recommendations')
        print(relevance(user, num))
