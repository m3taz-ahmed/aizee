**Title:** I built a policy gate for Claude Code hooks so my agent can't `git add .env` anymore — free tool, sharing in case it's useful

**Body:**

I built this myself (solo project) with Claude Code doing most of the implementation with me — roughly 60% of the ~8,000-test codebase was pair-written with Claude, which is also why it ended up as a Claude Code hooks integration first.

What it is: Claude Code hooks fire *before* the tool call executes. I wrote a small policy kernel that sits on that hook path — every Bash/Edit/Write/git call gets checked before it runs and returns allow / ask / deny / modify / observe. So when the agent decides `git add .` is a good idea, the `.env` line gets denied at the gate rather than argued with in a prompt.

How Claude helped: I described the failure modes I'd hit (agent committing secrets, "fixing" tests by deleting them, a prompt-injected README trying to get an agent to curl a URL) and Claude and I iterated on which checks are cheap-enough to run on every hook call. The regex injection detector and the verdict schema came out of those sessions. Claude also wrote most of the test harness, which is the only reason there's a 100% coverage floor on the gated surface.

It's free and open source (MIT): `pip install aizee`, then `aizee bootstrap --target ~/.aizee` wires the hooks into Claude Code / Cursor automatically. Repo: https://github.com/m3taz-ahmed/aizee — works without an account, runs locally.

Still figuring out which verdict is most useful day-to-day — I use `ask` for shell commands and `deny` for the credential paths. Curious what others gate on.
