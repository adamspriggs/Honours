
# Honours  
  In partial completion of COMP 4905 at Carleton University for Olga Baysal and in partnership with Lance Wang. 
### What this project is  
  
This python program will run through all or specified users Github Repositories and return a  
list of tuples with the Github Repo ID then the relevance score of that user to that repository. It uses Repopal's implementation outlined in this [paper](https://xin-xia.github.io/publication/saner17.pdf).  
This program takes in a set of repositories from the MongoDB supplied by Lance Wang in efforts  
to aid in his Masters Thesis research. [TBD link](n.a.)  
  
  
### How to run the project  
  
This program requires a running MongoDB on the localhost machine (or the location of the database  
can be changed in the code). It can be run with 'python main.py' with the following parameters:  
  
1. To view all users from the study's recommendation in 'output.txt'  
> python main.py -a/--all  
2. To view a specific user's recommendations  
> python main.py -u/--user <user ID>  
3. To specify the number of recommendations of a user  
> python main.py -n/--num <number>  
4. To list help
> python main.py -h/--help
  

### Sample script to run a list of users in a file for linux and windows  
NOTE: This will create mulitple files in the format output_<UserID>.txt  
  
1. Linux  
` cat sample_file.txt | while read line; do python main.py -u line; done `  
  
2. Windows  
` foreach($line in Get-Content .\sample_file.txt) {  
 $cmd = python main.py -u $line Start-Process $cmd }`

---
[Repopal](https://xin-xia.github.io/publication/saner17.pdf) authors
Yun Zhang<sup>1</sup>, David Lo<sup>2</sup>, Pavneet Singh Kochhar<sup>2</sup>, Xin Xia<sup>1</sup>, Quanlai Li<sup>3</sup>, and Jianling Sun<sup>1</sup>

<sup>1</sup> College of Computer Science and Technology, Zhejiang University, Hangzhou, China
<sup>2</sup> School of Information Systems, Singapore Management University, Singapore
<sup>3</sup> University of California, Berkeley, USA