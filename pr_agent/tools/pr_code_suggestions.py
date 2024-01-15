import copy
import textwrap
from functools import partial
from typing import Dict, List
from jinja2 import Environment, StrictUndefined

from pr_agent.algo.ai_handlers.base_ai_handler import BaseAiHandler
from pr_agent.algo.ai_handlers.litellm_ai_handler import LiteLLMAIHandler
from pr_agent.algo.pr_processing import get_pr_diff, get_pr_multi_diffs, retry_with_fallback_models
from pr_agent.algo.token_handler import TokenHandler
from pr_agent.algo.utils import load_yaml
from pr_agent.config_loader import get_settings
from pr_agent.git_providers import get_git_provider
from pr_agent.git_providers.git_provider import get_main_pr_language
from pr_agent.log import get_logger
from pr_agent.tools.pr_description import insert_br_after_x_chars


class PRCodeSuggestions:
    def __init__(self, pr_url: str, cli_mode=False, args: list = None,
                 ai_handler: partial[BaseAiHandler,] = LiteLLMAIHandler):

        self.git_provider = get_git_provider()(pr_url)
        self.main_language = get_main_pr_language(
            self.git_provider.get_languages(), self.git_provider.get_files()
        )

        # extended mode
        try:
            self.is_extended = self._get_is_extended(args or [])
        except:
            self.is_extended = False
        if self.is_extended:
            num_code_suggestions = get_settings().pr_code_suggestions.num_code_suggestions_per_chunk
        else:
            num_code_suggestions = get_settings().pr_code_suggestions.num_code_suggestions

        self.ai_handler = ai_handler()
        self.patches_diff = None
        self.prediction = None
        self.cli_mode = cli_mode
        self.vars = {
            "title": self.git_provider.pr.title,
            "branch": self.git_provider.get_pr_branch(),
            "description": self.git_provider.get_pr_description(),
            "language": self.main_language,
            "diff": "",  # empty diff for initial calculation
            "num_code_suggestions": num_code_suggestions,
            "summarize_mode": get_settings().pr_code_suggestions.summarize,
            "extra_instructions": get_settings().pr_code_suggestions.extra_instructions,
            "commit_messages_str": self.git_provider.get_commit_messages(),
        }
        self.token_handler = TokenHandler(self.git_provider.pr,
                                          self.vars,
                                          get_settings().pr_code_suggestions_prompt.system,
                                          get_settings().pr_code_suggestions_prompt.user)

    async def run(self):
        data = {'code_suggestions': [{'relevant_file': 'pr_agent/tools/pr_update_changelog.py', 'suggestion_content': 'The `get_git_provider()` function is called twice in the `__init__` method of `PRUpdateChangelog` class. It would be more efficient to call this function once and store the result in a variable, then use this variable in the conditional statements.\n', 'existing_code': 'if isinstance(self.git_provider, GithubProvider):\n    self.git_provider = get_git_provider()(pr_url)\nelif isinstance(self.git_provider, GitLabProvider):\n    self.git_provider = get_git_provider()(pr_url, incremental=True)\n', 'improved_code': 'git_provider = get_git_provider()\nif isinstance(self.git_provider, GithubProvider):\n    self.git_provider = git_provider(pr_url)\nelif isinstance(self.git_provider, GitLabProvider):\n    self.git_provider = git_provider(pr_url, incremental=True)\n', 'relevant_lines_start': 22, 'relevant_lines_end': 25, 'label': 'performance'}, {'relevant_file': 'pr_agent/tools/pr_update_changelog.py', 'suggestion_content': 'The `run` method of `PRUpdateChangelog` class has duplicate code for `GithubProvider` and `GitLabProvider`. This can be refactored to a separate method that accepts a `git_provider` as an argument, reducing code duplication.\n', 'existing_code': 'if isinstance(self.git_provider, GithubProvider):\n    if get_settings().config.publish_output:\n        self.git_provider.publish_comment("Preparing changelog updates...", is_temporary=True)\nelif isinstance(self.git_provider, GitLabProvider):\n    # Add code for preparing changelog updates for GitLabProvider\n    pass\n', 'improved_code': 'def prepare_changelog_updates(self, git_provider):\n    if get_settings().config.publish_output:\n        git_provider.publish_comment("Preparing changelog updates...", is_temporary=True)\n\nif isinstance(self.git_provider, GithubProvider):\n    self.prepare_changelog_updates(self.git_provider)\nelif isinstance(self.git_provider, GitLabProvider):\n    # Add code for preparing changelog updates for GitLabProvider\n    pass\n', 'relevant_lines_start': 55, 'relevant_lines_end': 60, 'label': 'maintainability'}, {'relevant_file': 'pr_agent/tools/pr_update_changelog.py', 'suggestion_content': 'The `assert` statement in the `run` method of `PRUpdateChangelog` class can be replaced with a more descriptive exception. This would provide a more meaningful error message if the condition is not met.\n', 'existing_code': 'assert type(self.git_provider) in [GithubProvider, GitLabProvider], "Currently only Github and GitLab are supported"\n', 'improved_code': 'if type(self.git_provider) not in [GithubProvider, GitLabProvider]:\n    raise ValueError("Unsupported git provider. Currently only Github and GitLab are supported.")\n', 'relevant_lines_start': 52, 'relevant_lines_end': 52, 'label': 'enhancement'}, {'relevant_file': 'pr_agent/tools/pr_update_changelog.py', 'suggestion_content': 'The `CHANGELOG_LINES` constant is defined at the global scope but is only used within the `PRUpdateChangelog` class. It would be more appropriate to define it as a class attribute.\n', 'existing_code': 'CHANGELOG_LINES = 25\n', 'improved_code': 'class PRUpdateChangelog:\n    CHANGELOG_LINES = 25\n    ...\n', 'relevant_lines_start': 16, 'relevant_lines_end': 16, 'label': 'best practice'}, {'relevant_file': '.github/ISSUE_TEMPLATE/sweep-bugfix.yml', 'suggestion_content': 'The `id` attribute for the second textarea is `description2`, which is not very descriptive. Consider using a more meaningful `id`.\n', 'existing_code': 'id: description2\n', 'improved_code': 'id: additional_details\n', 'relevant_lines_start': 13, 'relevant_lines_end': 13, 'label': 'enhancement'}, {'relevant_file': '.github/ISSUE_TEMPLATE/sweep-feature.yml', 'suggestion_content': 'The `description` attribute for the textarea is "More details for Sweep", which is not very descriptive. Consider providing a more specific description.\n', 'existing_code': 'description: More details for Sweep\n', 'improved_code': 'description: Please provide more details about the feature you want to test.\n', 'relevant_lines_start': 10, 'relevant_lines_end': 10, 'label': 'enhancement'}, {'relevant_file': '.github/ISSUE_TEMPLATE/sweep-refactor.yml', 'suggestion_content': 'The `placeholder` attribute for the textarea is "We are migrating this function to ... version because ...", which is not very clear. Consider providing a more specific placeholder.\n', 'existing_code': 'placeholder: We are migrating this function to ... version because ...\n', 'improved_code': 'placeholder: We are migrating this function to version 2.0 because it provides better performance.\n', 'relevant_lines_start': 11, 'relevant_lines_end': 11, 'label': 'enhancement'}]}
        self.publish_summarizes_suggestions(data)
        # try:
        #     get_logger().info('Generating code suggestions for PR...')
        #     if get_settings().config.publish_output:
        #         self.git_provider.publish_comment("Preparing suggestions...", is_temporary=True)
        #
        #     get_logger().info('Preparing PR code suggestions...')
        #     if not self.is_extended:
        #         await retry_with_fallback_models(self._prepare_prediction)
        #         data = self._prepare_pr_code_suggestions()
        #     else:
        #         data = await retry_with_fallback_models(self._prepare_prediction_extended)
        #     if (not data) or (not 'code_suggestions' in data):
        #         get_logger().info('No code suggestions found for PR.')
        #         return
        #
        #     if (not self.is_extended and get_settings().pr_code_suggestions.rank_suggestions) or \
        #             (self.is_extended and get_settings().pr_code_suggestions.rank_extended_suggestions):
        #         get_logger().info('Ranking Suggestions...')
        #         data['code_suggestions'] = await self.rank_suggestions(data['code_suggestions'])
        #
        #     if get_settings().config.publish_output:
        #         get_logger().info('Pushing PR code suggestions...')
        #         self.git_provider.remove_initial_comment()
        #         if get_settings().pr_code_suggestions.summarize:
        #             get_logger().info('Pushing summarize code suggestions...')
        #             self.publish_summarizes_suggestions(data)
        #         else:
        #             get_logger().info('Pushing inline code suggestions...')
        #             self.push_inline_code_suggestions(data)
        # except Exception as e:
        #     get_logger().error(f"Failed to generate code suggestions for PR, error: {e}")

    async def _prepare_prediction(self, model: str):
        get_logger().info('Getting PR diff...')
        self.patches_diff = get_pr_diff(self.git_provider,
                                        self.token_handler,
                                        model,
                                        add_line_numbers_to_hunks=True,
                                        disable_extra_lines=True)

        get_logger().info('Getting AI prediction...')
        self.prediction = await self._get_prediction(model)

    async def _get_prediction(self, model: str):
        variables = copy.deepcopy(self.vars)
        variables["diff"] = self.patches_diff  # update diff
        environment = Environment(undefined=StrictUndefined)
        system_prompt = environment.from_string(get_settings().pr_code_suggestions_prompt.system).render(variables)
        user_prompt = environment.from_string(get_settings().pr_code_suggestions_prompt.user).render(variables)
        if get_settings().config.verbosity_level >= 2:
            get_logger().info(f"\nSystem prompt:\n{system_prompt}")
            get_logger().info(f"\nUser prompt:\n{user_prompt}")
        response, finish_reason = await self.ai_handler.chat_completion(model=model, temperature=0.2,
                                                                        system=system_prompt, user=user_prompt)

        if get_settings().config.verbosity_level >= 2:
            get_logger().info(f"\nAI response:\n{response}")

        return response

    def _prepare_pr_code_suggestions(self) -> Dict:
        review = self.prediction.strip()
        data = load_yaml(review,
                         keys_fix_yaml=["relevant_file", "suggestion_content", "existing_code", "improved_code"])
        if isinstance(data, list):
            data = {'code_suggestions': data}

        # remove invalid suggestions
        suggestion_list = []
        for i, suggestion in enumerate(data['code_suggestions']):
            if suggestion['existing_code'] != suggestion['improved_code']:
                suggestion_list.append(suggestion)
            else:
                get_logger().debug(
                    f"Skipping suggestion {i + 1}, because existing code is equal to improved code {suggestion['existing_code']}")
        data['code_suggestions'] = suggestion_list

        return data

    def push_inline_code_suggestions(self, data):
        code_suggestions = []

        if not data['code_suggestions']:
            get_logger().info('No suggestions found to improve this PR.')
            return self.git_provider.publish_comment('No suggestions found to improve this PR.')

        for d in data['code_suggestions']:
            try:
                if get_settings().config.verbosity_level >= 2:
                    get_logger().info(f"suggestion: {d}")
                relevant_file = d['relevant_file'].strip()
                relevant_lines_start = int(d['relevant_lines_start'])  # absolute position
                relevant_lines_end = int(d['relevant_lines_end'])
                content = d['suggestion_content'].rstrip()
                new_code_snippet = d['improved_code'].rstrip()
                label = d['label'].strip()

                if new_code_snippet:
                    new_code_snippet = self.dedent_code(relevant_file, relevant_lines_start, new_code_snippet)

                if get_settings().pr_code_suggestions.include_improved_code:
                    body = f"**Suggestion:** {content} [{label}]\n```suggestion\n" + new_code_snippet + "\n```"
                    code_suggestions.append({'body': body, 'relevant_file': relevant_file,
                                             'relevant_lines_start': relevant_lines_start,
                                             'relevant_lines_end': relevant_lines_end})
                else:
                    if self.git_provider.is_supported("create_inline_comment"):
                        body = f"**Suggestion:** {content} [{label}]"
                        comment = self.git_provider.create_inline_comment(body, relevant_file, "",
                                                                          absolute_position=relevant_lines_end)
                        if comment:
                            code_suggestions.append(comment)
                    else:
                        get_logger().error("Inline comments are not supported by the git provider")
            except Exception:
                if get_settings().config.verbosity_level >= 2:
                    get_logger().info(f"Could not parse suggestion: {d}")

        if get_settings().pr_code_suggestions.include_improved_code:
            is_successful = self.git_provider.publish_code_suggestions(code_suggestions)
        else:
            is_successful = self.git_provider.publish_inline_comments(code_suggestions)
        if not is_successful:
            get_logger().info("Failed to publish code suggestions, trying to publish each suggestion separately")
            for code_suggestion in code_suggestions:
                if get_settings().pr_code_suggestions.include_improved_code:
                    self.git_provider.publish_code_suggestions([code_suggestion])
                else:
                    self.git_provider.publish_inline_comments([code_suggestion])

    def dedent_code(self, relevant_file, relevant_lines_start, new_code_snippet):
        try:  # dedent code snippet
            self.diff_files = self.git_provider.diff_files if self.git_provider.diff_files \
                else self.git_provider.get_diff_files()
            original_initial_line = None
            for file in self.diff_files:
                if file.filename.strip() == relevant_file:
                    original_initial_line = file.head_file.splitlines()[relevant_lines_start - 1]
                    break
            if original_initial_line:
                suggested_initial_line = new_code_snippet.splitlines()[0]
                original_initial_spaces = len(original_initial_line) - len(original_initial_line.lstrip())
                suggested_initial_spaces = len(suggested_initial_line) - len(suggested_initial_line.lstrip())
                delta_spaces = original_initial_spaces - suggested_initial_spaces
                if delta_spaces > 0:
                    new_code_snippet = textwrap.indent(new_code_snippet, delta_spaces * " ").rstrip('\n')
        except Exception as e:
            if get_settings().config.verbosity_level >= 2:
                get_logger().info(f"Could not dedent code snippet for file {relevant_file}, error: {e}")

        return new_code_snippet

    def _get_is_extended(self, args: list[str]) -> bool:
        """Check if extended mode should be enabled by the `--extended` flag or automatically according to the configuration"""
        if any(["extended" in arg for arg in args]):
            get_logger().info("Extended mode is enabled by the `--extended` flag")
            return True
        if get_settings().pr_code_suggestions.auto_extended_mode:
            get_logger().info("Extended mode is enabled automatically based on the configuration toggle")
            return True
        return False

    async def _prepare_prediction_extended(self, model: str) -> dict:
        get_logger().info('Getting PR diff...')
        patches_diff_list = get_pr_multi_diffs(self.git_provider, self.token_handler, model,
                                               max_calls=get_settings().pr_code_suggestions.max_number_of_calls)

        get_logger().info('Getting multi AI predictions...')
        prediction_list = []
        for i, patches_diff in enumerate(patches_diff_list):
            get_logger().info(f"Processing chunk {i + 1} of {len(patches_diff_list)}")
            self.patches_diff = patches_diff
            prediction = await self._get_prediction(model)
            prediction_list.append(prediction)
        self.prediction_list = prediction_list

        data = {}
        for prediction in prediction_list:
            self.prediction = prediction
            data_per_chunk = self._prepare_pr_code_suggestions()
            if "code_suggestions" in data:
                data["code_suggestions"].extend(data_per_chunk["code_suggestions"])
            else:
                data.update(data_per_chunk)
        self.data = data
        return data

    async def rank_suggestions(self, data: List) -> List:
        """
        Call a model to rank (sort) code suggestions based on their importance order.

        Args:
            data (List): A list of code suggestions to be ranked.

        Returns:
            List: The ranked list of code suggestions.
        """

        suggestion_list = []
        for suggestion in data:
            suggestion_list.append(suggestion)
        data_sorted = [[]] * len(suggestion_list)

        try:
            suggestion_str = ""
            for i, suggestion in enumerate(suggestion_list):
                suggestion_str += f"suggestion {i + 1}: " + str(suggestion) + '\n\n'

            variables = {'suggestion_list': suggestion_list, 'suggestion_str': suggestion_str}
            model = get_settings().config.model
            environment = Environment(undefined=StrictUndefined)
            system_prompt = environment.from_string(get_settings().pr_sort_code_suggestions_prompt.system).render(
                variables)
            user_prompt = environment.from_string(get_settings().pr_sort_code_suggestions_prompt.user).render(variables)
            if get_settings().config.verbosity_level >= 2:
                get_logger().info(f"\nSystem prompt:\n{system_prompt}")
                get_logger().info(f"\nUser prompt:\n{user_prompt}")
            response, finish_reason = await self.ai_handler.chat_completion(model=model, system=system_prompt,
                                                                            user=user_prompt)

            sort_order = load_yaml(response)
            for s in sort_order['Sort Order']:
                suggestion_number = s['suggestion number']
                importance_order = s['importance order']
                data_sorted[importance_order - 1] = suggestion_list[suggestion_number - 1]

            if get_settings().pr_code_suggestions.final_clip_factor != 1:
                max_len = max(
                    len(data_sorted),
                    get_settings().pr_code_suggestions.num_code_suggestions,
                    get_settings().pr_code_suggestions.num_code_suggestions_per_chunk,
                )
                new_len = int(0.5 + max_len * get_settings().pr_code_suggestions.final_clip_factor)
                if new_len < len(data_sorted):
                    data_sorted = data_sorted[:new_len]
        except Exception as e:
            if get_settings().config.verbosity_level >= 1:
                get_logger().info(f"Could not sort suggestions, error: {e}")
            data_sorted = suggestion_list

        return data_sorted

    def publish_summarizes_suggestions(self, data: Dict):
        try:
            pr_body = "## PR Code Suggestions\n\n"

            language_extension_map_org = get_settings().language_extension_map_org
            extension_to_language = {}
            for language, extensions in language_extension_map_org.items():
                for ext in extensions:
                    extension_to_language[ext] = language

            pr_body += "<table>"
            header = f"Suggestions"
            delta = 65
            header += "&nbsp; " * delta
            pr_body += f"""<thead><tr><th></th><th>{header}</th></tr></thead>"""
            pr_body += """<tbody>"""
            suggestions_labels = dict()
            # add all suggestions related to to each label
            for suggestion in data['code_suggestions']:
                label = suggestion['label'].strip().strip("'").strip('"')
                if label not in suggestions_labels:
                    suggestions_labels[label] = []
                suggestions_labels[label].append(suggestion)

            for label, suggestions in suggestions_labels.items():
                pr_body += f"""<tr><td><strong>{label}</strong></td>"""
                pr_body += f"""<td><table>"""
                for suggestion in suggestions:

                    relevant_file = suggestion['relevant_file'].strip()
                    relevant_lines_start = int(suggestion['relevant_lines_start'])
                    relevant_lines_end = int(suggestion['relevant_lines_end'])
                    code_snippet_link = self.git_provider.get_line_link(relevant_file, relevant_lines_start,
                                                                        relevant_lines_end)
                    # add html table for each suggestion

                    suggestion_content = suggestion['suggestion_content'].rstrip().rstrip()
                    suggestion_content = insert_br_after_x_chars(suggestion_content, 90)
                    # pr_body += f"<tr><td><details><summary>{suggestion_content}</summary>"
                    existing_code = suggestion['existing_code'].rstrip()
                    improved_code = suggestion['improved_code'].rstrip()
                    language_name = "python"
                    extension_s = suggestion['relevant_file'].rsplit('.')[-1]
                    if extension_s and (extension_s in extension_to_language):
                        language_name = extension_to_language[extension_s]
                    example_code = ""
                    if self.git_provider.is_supported("gfm_markdown"):
                        example_code = "<details> <summary> Example code:</summary>\n\n"
                        example_code += f"___\n\n"
                    example_code += f"Existing code:\n```{language_name}\n{existing_code}\n```\n"
                    example_code += f"Improved code:\n```{language_name}\n{improved_code}\n```\n"
                    if self.git_provider.is_supported("gfm_markdown"):
                        example_code += "</details>\n"
                    pr_body += f"""
<tr>
  <td>
  
  
**{suggestion_content}**
    
[{relevant_file} [{relevant_lines_start}-{relevant_lines_end}]]({code_snippet_link})

{example_code}
  </td>

</tr>                    
"""
                pr_body += """</table></td></tr>"""
            pr_body += """</tr></tbody></table>"""
            # for s in data['code_suggestions']:
            #     try:
            #         extension_s = s['relevant_file'].rsplit('.')[-1]
            #         code_snippet_link = self.git_provider.get_line_link(s['relevant_file'], s['relevant_lines_start'],
            #                                                             s['relevant_lines_end'])
            #         label = s['label'].strip()
            #         data_markdown += f"\n💡 [{label}]\n\n**{s['suggestion_content'].rstrip().rstrip()}**\n\n"
            #         if code_snippet_link:
            #             data_markdown += f" File: [{s['relevant_file']} ({s['relevant_lines_start']}-{s['relevant_lines_end']})]({code_snippet_link})\n\n"
            #         else:
            #             data_markdown += f"File: {s['relevant_file']} ({s['relevant_lines_start']}-{s['relevant_lines_end']})\n\n"
            #         if self.git_provider.is_supported("gfm_markdown"):
            #             data_markdown += "<details> <summary> Example code:</summary>\n\n"
            #             data_markdown += f"___\n\n"
            #         language_name = "python"
            #         if extension_s and (extension_s in extension_to_language):
            #             language_name = extension_to_language[extension_s]
            #         data_markdown += f"Existing code:\n```{language_name}\n{s['existing_code'].rstrip()}\n```\n"
            #         data_markdown += f"Improved code:\n```{language_name}\n{s['improved_code'].rstrip()}\n```\n"
            #         if self.git_provider.is_supported("gfm_markdown"):
            #             data_markdown += "</details>\n"
            #         data_markdown += "\n___\n\n"
            #
            #         pr_body += f"""<tr><td><b>{label}</b></td><td><a href="{code_snippet_link}">{s['relevant_file']}</a></td></tr>"""
            #         # in the right side of the table, add two collapsable sections with the existing and improved code
            #         pr_body += f"""<tr><td></td><td><details><summary>Existing code</summary><pre><code>{s['existing_code'].rstrip()}</code></pre></details></td></tr>"""
            #         pr_body += f"""<tr><td></td><td><details><summary>Improved code</summary><pre><code>{s['improved_code'].rstrip()}</code></pre></details></td></tr>"""
            #
            #
            #     except Exception as e:
            #         get_logger().error(f"Could not parse suggestion: {s}, error: {e}")
            self.git_provider.publish_comment(pr_body)
        except Exception as e:
            get_logger().info(f"Failed to publish summarized code suggestions, error: {e}")
