# MP2 Report — AWM at Kenyon CMS

Maggie Grespin · Oct 5, 2026

## 1. What I built, and which decisions were mine

The goal of this project was to create a site for our Association of Women in Mathematics club. For the scope of the Mini-Project, currently the admin and editor consoles run solely on my own personal laptop.  The primary capabilities of the site are that AWM officers can post events and pages without learning HTML coding.

One decision I made was deciding on who got accounts and how the accounts got transferred. Originally, Claude recommended that every position holder should have their own account, and when the year ends, the accounts should be closed. However, I do not think the information on these posts and the websites is secret enough to have that level of security. We have our own Instagram account and every position holder uses the same generic login that has been passed down from the old exec team to the new exec team; I wanted to use this same logic for the website logins. Therefore, I told Claude that each position has their own login, not each person, and the account is just transferred from year to year. This means that the co-Presidents and co-VPs share a login and the social and treasury positions have their own logins. Similarly to the Instagram the password will be transferred to the upcoming position holder in the spring semester.

Another decision that was mine was on the actual content of a typical AWM "post". I think AWM is more boring than Claude anticipates because we only have one type of meeting, and it is practically always the same day and time, without fail. So I explained that "the most common 99% of the time will be the weekly Monday study hall reminder, but other things can be posted, such as a cancelled meeting, snack update etc." This was helpful because after this input, Claude had a more clear understanding of the organization. 

A third decision that was mine was the content on the 3 pages. Claude's original plan was to have 3 pages:  Study Hall, Snacks, and Join page. However, I decided to change up the content on the pages:

1. the basic study hall information and where the latest post lives
2. an about us section for the officers,
3. joining and snack information and recommendation form

These decisions were all made in round one of grill-with-docs, I found that after Claude had this initial input the recommendations were very tuned in to my vision for the site. Therefore, for rounds two and three I mainly just went with Claude's informed recommendations.

## 2. Where the AI drifted, and what caught it

I think the best example of where AI drifted was during T05 (issue #6) when Claude added behavior that wasn’t in the spec. Luckily, when I ran /code-review right after T05 was built it caught this drift. The review notified me of this drift after comparing the spec and the code by saying: "Not asked for: unknown filter values (for example ?status=bogus) are silently ignored and show everything." I decided just to keep this behavior as it was harmless, I explained more in my GitHub comment. 

## 3. Skills, prompts, and resources I used

Primarily, the skills I used were the ones from the Matt Pocock set up. These include /grill-with-docs, /to-spec, /to-tickets, /implement + /tdd, /code-review, and  /handoff. /grill-with-docs asked me questions about AWM based on my client brief and WordPress field trip; this was done before anything was coded. The next step was /to-spec, this split my answers from the grilling into a plan, then /to-tickets split that even further into small doable tickets for an agent. /implement + /tdd were used on the tickets, the goal was to have tests that failed first, and then from there to make code to have those tests pass. /code-review had a fresh agent check the code against the original plan (spec); this review was what caught the drift I mention in section 2. /handoff summarizes the important information from the session so that a new agent can pick up from where we ended. /browse is the only non-Matt Pocock skill and it takes screenshots of a controlled browser. This skill helped me catch a bug in which most of the admin pages didn't have the CSS styling and it wasn’t caught until those screenshots were taken.

I think that the best prompt habit I learned throughout this project was always clearing the chats between topic changes. After learning about context rot, I truly believe this small step saved me a lot of headaches. Additionally it was helpful to have Claude pause before committing so that I could check to see if I understood the process and if I thought it was right. The resources I used for this project were sourced from Professor Chun. For this project he gave us a manual and a rubric that I heavily relied upon. We worked in the WordPress Playground to get an idea of how a CMS operates. Additionally, I used Claude Code and Claude Cowork to help guide me through the tougher processes. 



## 4. What I'd add next, and what the budget data told me

There are a couple of things I would do next, the first is add photos to the About page so that the executive members get more recognition and are easily identified. I would also continue with the last three tickets (T07-T09) and adjust the Accounts table layout (especially for the phone). I chose to edit the required parts of this project instead of adding on these optional pieces. 

	Honestly when talking about budgeted tokens I greatly overestimated this project. I was about 3-5x under my proposed budget; I estimated each ticket would use 25-30% of a 5h window per ticket but on average it used about 8%. The setup and pre-exercises accounted for the largest chunk of tokens, this is the “unlabelled” section that took up about 18% of my 5h window. The planning section of this project was projected to use 35% of my 5h window and it actually used 11%. Overall, this mini-project only used about 14% of my weekly cap when I thought it would use 30-45%. I am honestly surprised at this efficiency because I opted to use high thinking during the planning stages and I feared that would waste a lot of my tokens. I also originally planned to use Haiku for efficiency purposes but ended up not switching to it. An observation from the tickets is that T02 and T04 cost the most, both of them used about 11% of my 5h window. However, T03 had the most turns. This just shows that cost is not equivalent to chats sent.

Since I overestimated by so much I never had to use the plan I put in place if I was at risk of going over budget. Also, note about the budget plan: I accidentally wrote “ 225-2705” when I meant “225–270%.” I am glad I overestimated because I would much rather that than the alternative. This thinking is why I believe the overestimation happened in the first place. This was my first time doing anything like this, next time, I would base my budget off this project.

  
