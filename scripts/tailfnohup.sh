tail -1000f nohup.out |
jq --unbuffered -Rr '
fromjson? |
if .type=="item.started" and .item.type=="command_execution" then
  "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n▶ COMMAND\n\(.item.command)\n"
elif .type=="item.completed" and .item.type=="command_execution" then
  if .item.exit_code==0 then
    "✓ OK\n\(.item.aggregated_output // "")"
  else
    "❌ FAILED [exit=\(.item.exit_code)]\n\(.item.aggregated_output // "")"
  end
elif .type=="item.completed" and .item.type=="agent_message" then
  "\n🤖 CODEX\n\(.item.text // .item.content // "")"
elif .type=="error" then
  "\n❌ ERROR\n\(.message // .error // "")"
else
  empty
end
'
