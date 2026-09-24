# Claude Opus 5.5: The Upgrade Hidden in the Bill

## 01_hook | The upgrade hidden in the bill
Forty percent cheaper. That's Anthropic's headline for Claude Opus five point five. But look at the actual token prices: those fell twenty percent. Both numbers can be right. The difference is how much work the model does before it finishes your job.

So let's follow the bill. We'll look at the release examples, what the benchmark charts actually measure, and the changes that matter before you switch. These are published results, with our analysis, rather than our own model test.

## 02_cost | Why twenty and forty are different
Start with the simple part. The listed price is four dollars for a million input tokens and twenty dollars for a million output tokens. Previously, those were five and twenty-five. Tokens are the pieces of text the service processes. Input is what goes in; output is what comes back, including billable reasoning where applicable.

For a deliberately simple example, imagine a job with a million ordinary input tokens and a million output tokens. At those rates, thirty dollars becomes twenty-four. That's a twenty percent reduction. This example excludes caching, tools and other charges. It isn't a prediction of your bill.

Now add the amount of work. If a model solves the same problem with fewer attempts, it may process less text overall. A cheaper rate multiplied by less work can produce a bigger saving. That's why the price per token and the cost of a completed task need separate labels on a chart.

There's another part: cached input. When a service can reuse previously processed context, that read has its own price. Opus five point five lists twenty cents per million cached input tokens, versus fifty cents previously. That can matter in long sessions. But you can't apply that rate to every token and call the whole task almost free. The mix matters.

## 03_coding | Less back-and-forth on real work
The interesting coding claim is about finishing a longer job with less back-and-forth. GitHub says its early tests saw comparable task resolution to Opus five, using significantly fewer steps and tokens. It also reports recovery from errors during multistep tasks. That is a more useful description than simply saying an agent is smarter.

Picture a change that touches the login page, a server endpoint and a test. The first edit might be straightforward. The expensive part can be discovering that one assumption was wrong, tracing the consequences, and fixing the places affected. This is an illustration of the workflow, not a task we ran on the new model.

To judge a coding demo, watch the checks after the edit. Did the existing tests run? Was the failure actually explained? Did the model change the test just to make the green check appear? A fast finished screen doesn't answer those questions. The useful footage is often the unglamorous bit in the middle.

GitHub has added the model to Copilot, with access depending on your plan and rollout. So the place to evaluate it may be the editor you already use. Keep the task and starting files the same when comparing models. Otherwise you're comparing two different problems and giving the winner a trophy anyway.

## 04_charts | How to read the benchmark charts
These charts need two readings. Up means a stronger score on the named evaluation. Left means lower cost for that evaluation. A point closer to the upper left is attractive because it combines both. But first read the axes. Some charts use success percentages; others use rating systems. Those are different units.

Artificial Analysis independently reports a score of fifty-eight on its Intelligence Index at maximum effort, the highest it had measured at release. That's an index score. It doesn't mean the model gets fifty-eight percent of everything right. The same report gives fifty-nine point six percent on Terminal Bench four, level with its reported Astra result.

Terminal Bench evaluates work performed through a command line. Imagine navigating files, using tools and completing a task, rather than answering a single quiz question. A strong result there is useful evidence for that kind of work. It can't tell you whether the model will write the email you like or understand your particular company spreadsheet.

Also check the effort setting, tools and test setup beside the chart. A model's name alone doesn't describe the full run. My reading is that the independent results make this release worth testing. The decision for your project still needs one more column: did the result satisfy your own requirements?

## 05_work | A polished answer still needs evidence
One launch example makes that point nicely. Anthropic describes an internal research test where invented figures or quotations caused a report to fail. Sixteen of eighteen Opus five point five reports passed its threshold. That is a result from a particular company-run test, not a promise that your next report will be accurate.

For ordinary work, the useful question is whether you can follow an answer back to its evidence. Suppose you're comparing suppliers. You need to know which price came from which document, when it applied, and whether shipping was included. A beautifully written comparison with those details mixed up is still the wrong comparison.

Before asking for a presentation, I'd ask for the underlying table: each claim, its source, and any missing information. Then I'd inspect a few consequential entries myself. That's a proposed workflow, not a hidden benchmark. It makes the final slides easier to review because the reasoning has something concrete to attach to.

The same distinction applies to an impressive launch demo. The visible spreadsheet or presentation shows an output. It doesn't show every assumption that produced it. Look for the inputs and the verification step. Those are the parts that tell you whether you could trust a similar result with your own work.

## 06_communication | Clearer answers are part of the product
Cursor's model notes call out clearer communication and less over-explanation during long agent sessions. They also recommend the high thinking variant for their strongest results. That second detail matters: a product's recommended setting can differ from the model's default setting. We'll come back to that when we talk about trying it.

Clearer writing sounds like a small upgrade until you're reviewing a long session. Here's an original example. One answer says, the process encountered an inconsistency in the temporal aggregation logic. Another says, the report skipped the last day of the month. The second gives you somewhere to look. Neither sentence, by itself, proves the diagnosis.

What I'd want next is the relevant evidence and the smallest useful explanation. Show the date range. Show the condition that excluded the records. Explain the repair and how you checked it. The answer can be short without becoming vague, and detailed without turning into a wall of text.

When you try the model, give it a writing instruction you actually care about. For example: start with what changed, explain unfamiliar terms, and put unresolved questions at the end. Then see whether it follows that instruction across a whole task. A good first response is encouraging; consistency is what makes it pleasant to work with.

## 07_settings | The setting changes the comparison
The documentation lists medium as the default effort for Opus five point five. Effort controls how much reasoning the model applies. Turning it up may help with a difficult problem, but that makes it important to compare both the outcome and the cost. Maximum isn't automatically the right starting point for every task.

A reasonable trial is one familiar job at medium, followed by the same job at a higher setting if the first result misses something important. Keep the instructions and success criteria steady. If both results pass, you can compare time and cost. If only one passes, the cheaper failed attempt hasn't saved you much.

There's also fast mode. The product page describes up to two and a half times faster output, at higher listed rates: eight dollars per million input tokens and forty per million output tokens. That is a speed option with a price tradeoff. It isn't the same thing as the standard model's lower pricing.

And output speed is only part of waiting for an agent. Your workflow may also spend time on searches, tools and tests. When you evaluate the upgrade, measure the time until you have something usable. A stream of fast text can look productive while the actual task is still unfinished.

## 08_migration | Check this before switching an automation
If you use Claude through an app, you can mostly focus on choosing the model and checking its results. If you've built an automation around the API, read the migration guide first. It documents breaking changes. Replacing the model name alone may leave your existing requests incompatible.

Thinking is always on. The old setting that disables it isn't accepted. Forced tool selection also changes: the guide tells developers to replace the affected tool-choice settings. Some computer-use integrations need a newer toolset, depending on the platform. Check the exact platform instructions rather than copying a change meant for somebody else's setup.

Conversation handling matters too. Preserved thinking has rules about reusing prior context, and the response format around tool calls can affect what your interface displays. In plain English, your app needs to understand the messages it receives and preserve the conversation correctly. Otherwise a capable model can sit behind an integration that fails before it finishes anything.

I'd run the migration on a copy of a real workflow, including one tool failure and one retry. Check the final result, the logs and the bill. Once those look right, expand the trial. The official guide includes a checklist; use it alongside your own acceptance test, because your application is the part the model vendor hasn't seen.

## 09_decision | What would make it worth switching?
So the forty percent headline is a claim about typical workload cost, supported by changes in rates and efficiency. Your result depends on what you ask the model to do and how you run it. The practical upgrade would be getting work you can verify with fewer corrections and less waiting.

For someone already using an agent on code or documents, that makes Opus five point five an interesting candidate. Pick one job you know well, write down what a correct result needs, and compare the complete attempts. Record the fixes you had to make, not just the answer the model gave itself.

If the new model finishes that job well for less, you've found a useful upgrade. If it gives you a nicer explanation but still needs the same repairs, you've learned something too. The launch gets it onto the shortlist. Your actual work decides whether it stays there.
