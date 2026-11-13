#import "helpers.typ": todo, todo-inline

= Functional requirements <FunctionalRequirements>

#todo[AI-drafted text (Claude, 2026-11-08), kept only as a reference.
The AI-use statement in this thesis says that AI did not generate essential parts of the work.
Rewrite this chapter in your own words, check every claim against its source,
and list the use of AI in the AI Usage Report.]

This chapter lists what the system allows its users to do.
The system has three roles.
An _administrator_ manages users, datasets and permissions.
An _analyst_ and a _viewer_ chat with datasets;
they differ only in the permissions to see decrypted values that they receive by default.
A fourth party, the _operator_, prepares datasets with command-line tools on the server.

#todo[Draft written from the API (`api/routers/`) and the scripts on 2026-11-08.
Check it against the final code and add the requirement numbers to the use cases.]

== Accounts and permissions

- *FR-01.* A user can log in with an e-mail address and a password, and log out.
- *FR-02.* An administrator can create user accounts with the role administrator, analyst or viewer,
  list the accounts, and delete them.
- *FR-03.* An administrator can grant and revoke the permission of a user
  to see the decrypted values of a given entity type in a given dataset.
  An administrator can see all types.
  A new analyst receives permissions for names, e-mail addresses, telephone numbers, locations and organisations
  in all existing datasets.

== Datasets

- *FR-04.* An administrator can create a dataset and set or delete its key.
- *FR-05.* An administrator can import the token map of a pseudonymised corpus into a dataset.
- *FR-06.* An administrator can assign a language model to a dataset.
- *FR-07.* An operator can pseudonymise a collection of documents
  and register it as a dataset with a retrieval index.

== Chat

- *FR-08.* A user can start a chat about a selected dataset, ask questions,
  and see the answer while it is being generated.
- *FR-09.* Personal data in a question are pseudonymised
  before the question is stored or sent to the model.
- *FR-10.* For each question, the records of the selected dataset that are most relevant to it
  are given to the model, and only records of that dataset.
- *FR-11.* A token in an answer is shown as the original value
  if the user has the permission for its entity type;
  otherwise the token is shown.
- *FR-12.* A user can list, open and delete their own chats.

== Accountability and recovery

- *FR-13.* Every decryption of a token for a user is recorded
  with the user, the token, its entity type, the dataset and the time.
- *FR-14.* A holder of the dataset key can restore a tokenised file to its original text with a command-line tool.
