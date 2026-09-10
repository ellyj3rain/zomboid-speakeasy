# Decisions

The dataset this project exists to make. Record 24 ratified where rows
come from and what a row is; this directory carries that shape. The
first rows are here, proposed in record 28 and ratified by the
operator in record 29: `work-words.jsonl`, 112 rows of work words.

A second target is proposed in record 30: `trade-hinges.jsonl`,
78 rows where the person's own trade is the situation's hinge,
authored from an engine dump of the county's elections.

## Where a row comes from

A person's own SAO record is put to a language model - their traits,
conditions, habits, occupation, age, history and lessons, plus the
belief set they hold at that moment - and the model decides **as that
person, in that situation, among the options actually available**.

Rows arrive as a proposal the operator rules on. AI-written behaviour
is not ratified intent, and a dataset does not become intent by being
large.

## What a row is

Four things, derived from the decisions SAO's people actually face,
read off the code rather than imagined.

**The person.** What SAO already carries and can hand over unchanged:
the eight traits, the wanted circle, conditions and habits, occupation
and its class, age, the formative events of their history, the lessons
they hold, and their standing toward whoever else is in the situation.

**The situation.** Their belief set at that moment, with each belief's
provenance and age - what they have seen, been told, heard, or lived,
and how long ago. This is the half that keeps the model honest: a
cognition that decides on facts the person does not hold is the
omniscience failure, and it is the same defect whether a table or a
model produced it.

**The options.** What was actually available, which the consumer
supplies. A model choosing from options the county cannot perform
produces a row nothing can use.

**The choice, and its words.** Which option, and - where a group has
created something that did not exist, a position or a relationship to a
place - the word that group uses for it.

## What this is for

It replaces the places the consumer currently authors a list: the work
words a company deals from, the creed names, the shape of a group's
relationship to a place. A group must be able to create a position
because it needed one and have its own word for it, and no table can
stand in for that.

## How it is checked

The consumer's county sweep measures whether the resulting
distributions are sane. **The distribution is the check and it is never
a border**, because a border is a point and a county is a distribution.

## What does not happen here

No row is harvested from a player. Nothing reaches an external service
at play time - what ships is distilled into a small model inside the
consumer's own tree, and no capability requires another mod.
