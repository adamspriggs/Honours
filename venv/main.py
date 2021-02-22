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
watching = mongo_db['watching']

DEFAULT_NUM_RECOMMENDATIONS = 10

#98036093
def relevance(user, number_of_recommendations=DEFAULT_NUM_RECOMMENDATIONS):
    # TEST Repo Set
    # Test ONE repo first
    #repoQ = [readmes_gensim.find_one({"id": user}, {"_id": 0, "id": 1, "readme_tfidf":1, "watchers":1})]
    repoQ = watching.find({"user_id": user}, {"_id": 0, "repo_id": 1})
    repo_set = watching.find({}, {"_id":0, "repo_id" : 1}).distinct("repo_id")


    # repo_ids = [x['repo_id'] for x in watching.find({}, {"_id":0, "repo_id":1})]
    # repo_set = []
    # for x in repo_ids:
    #     val = readmes_gensim.find_one({"id": x}, {"_id" : 0})
    #     if val != None:
    #         repo_set.append(val)

    suggestion = []
    counter = 0

    #212268

    print("Starting relevance...")
    # Repo's to test again
    for x in repoQ:
        x_repo = readmes_gensim.find_one({"id": x['repo_id']}, {"_id": 0, "id": 1, "readme_tfidf": 1})
        if x_repo is None:
            continue
        for y in repo_set:
            y_repo = readmes_gensim.find_one({"id": y}, {"_id":0, "id":1, "readme_tfidf":1})
            if y_repo is None:
                continue
            counter += 1
            if counter % 1000 == 0:
                print(counter) #DOESNT WORK
            with concurrent.futures.ThreadPoolExecutor() as executor:
                #c1 = executor.submit(compute_readme_relevance, x_repo, y_repo)
                #c2 = executor.submit(compute_time_relevance, x_repo, y_repo)
                c3 = executor.submit(compute_stargazer_user_relevance, x_repo, y_repo)

                relevance = c3.result()#c1.result() * c2.result() * c3.result()
                suggestion.append((y, relevance))
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
    repo_one = first_repo['id']
    repo_two = second_repo['id']

    if repo_one == repo_two:
        return 0

    total = 0
    first = [x for x in watching.find({'repo_id': repo_one}, {"_id":0, "user_id":1})]
    second = [x for x in watching.find({'repo_id': repo_two}, {"_id":0, "user_id":1})]
    for x in first:
        user_one = users.find_one({"user_id": x}, {"_id": 0, "repopal_user_similarities": 1})

        if user_one is None:
            continue

        for y in second:
            val = user_one['repopal_user_similarities'][y]
            if val is None:
                continue
            else:
                total += val

    return total / len(first + second)

def compute_time_relevance(first_repo, second_repo):
    repo_one = watching.find({"repo_id":first_repo['id']}, {"_id":0, "user_id":1, "created_at":1})
    repo_two = watching.find({"repo_id":second_repo['id']}, {"_id":0 ,"user_id":1, "created_at":1})

    if not repo_one or not repo_two:
        return 0
    if repo_one == repo_two:
        return 0

    inter = intersection(watching.find({"repo_id":first_repo['id']}, {"_id":0, "user_id":1}).distinct("user_id"), watching.find({"repo_id":second_repo['id']}, {"_id":0, "created_at":1}).distinct("user_id"))

    if not inter:
        return 0

    total = 0
    sum = 0
    dates = []

    for each in inter:
        total += 1
        x = watching.find_one({"repo_id":first_repo['id'], "user_id": each}, {"_id":0, "user_id":1, "created_at":1})
        y = watching.find_one({"repo_id":second_repo['id'], "user_id": each}, {"_id":0 ,"user_id":1, "created_at":1})
        date_one = datetime.strptime(y['created_at'], "%Y/%m/%d %H:%M:%S")
        date_two = datetime.strptime(x['created_at'], "%Y/%m/%d %H:%M:%S")
        bot = abs((date_two - date_one).seconds/3600)
        if bot == 0:
            sum += 0
        else:
            sum += (1 / bot)


    average = sum / total
    return average

def intersection(l1,l2):
    return set(l1).intersection(l2)

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
        #print(relevance(user, num))
        relevance(user, num)
