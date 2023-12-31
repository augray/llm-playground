# Standard Library
import os
from dataclasses import dataclass
from typing import Optional, Tuple

# Third-party
from datasets import Dataset
from peft import PeftModel
from transformers import AutoModelForSeq2SeqLM, PreTrainedTokenizerBase

# Sematic
import sematic
from zzz.examples.summarization_finetune.train_eval import (
    DatasetConfig,
    EvaluationResults,
    HuggingFaceModelReference,
    ModelSelection,
    ModelType,
    TrainingConfig,
    evaluate,
    export_model,
)
from zzz.examples.summarization_finetune.train_eval import (
    load_tokenizer as do_load_tokenizer,
)
from zzz.examples.summarization_finetune.train_eval import prepare_data
from zzz.examples.summarization_finetune.train_eval import train as do_train
from sematic.types import HuggingFaceStoredModel as StoredModel


@dataclass(frozen=True)
class ResultSummary:
    source_model: HuggingFaceModelReference
    trained_model: StoredModel
    evaluation_results: EvaluationResults
    pushed_model_reference: Optional[HuggingFaceModelReference]


@sematic.func
def pick_model(model: ModelSelection) -> Tuple[HuggingFaceModelReference, ModelType]:
    if model.value.startswith("flan"):
        size = model.value.replace("flan_", "")
        return (
            HuggingFaceModelReference(owner="google", repo=f"flan-t5-{size}"),
            ModelType.seq_to_seq,
        )
    else:
        name = model.value.replace("_", "-")
        return (
            HuggingFaceModelReference(owner="tiiuae", repo=name),
            ModelType.causal,
        )


@sematic.func
def load_tokenizer(
    model_reference: HuggingFaceModelReference,
) -> PreTrainedTokenizerBase:
    return do_load_tokenizer(model_reference.to_string())


@sematic.func
def train(
    model_reference: HuggingFaceModelReference,
    training_config: TrainingConfig,
    train_data: Dataset,
    eval_data: Dataset,
    tokenizer: PreTrainedTokenizerBase,
) -> StoredModel:
    model = do_train(
        model_reference.to_string(),
        training_config,
        train_data,
        eval_data,
        tokenizer,
    )
    return StoredModel.store(model, training_config.storage_directory)


@sematic.func
def eval(
    model: StoredModel,
    eval_data: Dataset,
    tokenizer: PreTrainedTokenizerBase,
) -> EvaluationResults:
    return evaluate(model.load(), eval_data, tokenizer)


@sematic.func
def prepare_datasets(
    dataset_config: DatasetConfig,
    tokenizer: PreTrainedTokenizerBase,
    model_type: ModelType,
) -> Tuple[Dataset, Dataset]:
    train_dataset, test_dataset = prepare_data(dataset_config, tokenizer, model_type)
    return train_dataset, test_dataset


@sematic.func
def export(
    model: StoredModel,
    push_model_ref: HuggingFaceModelReference,
) -> HuggingFaceModelReference:
    return export_model(model.load(), push_model_ref)


@sematic.func
def summarize(
    source_model: HuggingFaceModelReference,
    trained_model: StoredModel,
    evaluation_results: EvaluationResults,
    pushed_model_reference: Optional[HuggingFaceModelReference],
) -> ResultSummary:
    return ResultSummary(
        source_model=source_model,
        trained_model=trained_model,
        evaluation_results=evaluation_results,
        pushed_model_reference=pushed_model_reference,
    )


@sematic.func
def pipeline(
    training_config: TrainingConfig,
    dataset_config: DatasetConfig,
    export_reference: Optional[HuggingFaceModelReference],
) -> ResultSummary:
    model_ref, model_type = pick_model(training_config.model_selection)
    tokenizer = load_tokenizer(model_ref)
    train_data, test_data = prepare_datasets(dataset_config, tokenizer, model_type)
    model = train(model_ref, training_config, train_data, test_data, tokenizer)
    eval_results = eval(model, test_data, tokenizer)

    exported_model_reference = None
    if export_reference is not None:
        exported_model_reference = export(model, export_reference)

    return summarize(
        source_model=model_ref,
        trained_model=model,
        evaluation_results=eval_results,
        pushed_model_reference=exported_model_reference,
    )
