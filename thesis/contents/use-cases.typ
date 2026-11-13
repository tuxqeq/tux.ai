#import "helpers.typ": todo, todo-inline

= Use cases <UseCases>

This chapter describes how the actors of the system interact with it.

#todo[Use-case diagrams as vector graphics (not screenshots), split into small diagrams:
(1) administrator: manage users, manage datasets, manage permissions;
(2) analyst / viewer: log in, chat about a dataset, see decrypted answer;
(3) operator: prepare a dataset (generate or collect documents, pseudonymise, bootstrap the dataset).]

== Actors

#todo[Administrator, analyst, viewer, operator (see @FunctionalRequirements).]

== Selected use case scenarios

#todo[Detailed scenario "Ask a question about a person":
the user asks "What is John Smith's SSN?";
the question is pseudonymised (`[PERSON_x]'s SSN`);
records containing `[PERSON_x]` are retrieved;
the model answers with `[SSN_y]`;
the token is decrypted if the user may see SSN, otherwise shown as a token;
the decryption is logged.
Also: "Prepare a dataset" (operator).]
