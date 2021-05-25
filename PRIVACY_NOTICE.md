# What data does Synth collect?

For Synth to function fully Synth grabs guild id, user id, and channel id and links them together. Zero data is gathered on the names of users or the names of the channels. 

**ZERO DATA IS EVER SHARED OUTSIDE OF THE OWNER.** Contents of database may be purged depending if channels were deleted/the guild removed Synth.

## Owner Messages

When joining a guild a small small embed of basic guild stats notifies only the bot owner about the guild that Synth was updated. This helps make sure that the health of Synth is good and that if a massive guild shortly adds Synth that the database can be prepped for any errors. If you are worried about the data Synth sends to the owners look in `bot/cogs/owner.py`

Another message that gets sent to the owner is when a command error outs. The message contains where it was sent and what the content of the message was. Maintaining the bot requires a way to get easily notified of errors and what caused the error.

# How long will my data be kept?

By default data will be deleted after Synth is removed from a server or when data becomes invalid. On top of that data is automatically pruned to help minimize database storage. Unless bigger quotas were unlocked, data containing user and channel id gets stripped after 90 days. 
