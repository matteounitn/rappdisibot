#!bin/sh
if [[ -z "${token}" ]]; then
  echo "You have to insert a token to continue."
  exit 1
else
  python3 bot.py -t "${DEPLOY_ENV}"
fi
