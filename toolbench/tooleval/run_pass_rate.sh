# export CONVERTED_ANSWER_PATH=../../result2/test_instruction/
export CONVERTED_ANSWER_PATH=../../data/reproduction_data/model_predictions_converted
export SAVE_PATH=../../output/pass_rate_results
# export CANDIDATE_MODEL=gpt-4-turbo_dfs
# export CANDIDATE_MODEL=reassign_turbo
export CANDIDATE_MODEL=chatgpt_dfs
# export CANDIDATE_MODEL=toolllama_dfs_retriever
# export CANDIDATE_MODEL=gpt-4-0613_dfs
export API_POOL_FILE=../../openai_key.json
for i in 1
do
python eval_pass_rate.py \
    --converted_answer_path ${CONVERTED_ANSWER_PATH} \
    --save_path ${SAVE_PATH} \
    --reference_model ${CANDIDATE_MODEL} \
    --test_ids ../../data/test_query_ids/ \
    --max_eval_threads 10 \
    --evaluate_times 7
done
