import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly
from sklearn import metrics
from sklearn.metrics import precision_score,recall_score, f1_score, accuracy_score
import re
# Class to aggregate the grades of each section from a result file
class SectionGradeAggregator():
    def __init__(self, output_df_path, grade_col) -> None:
        self.pass_threshold = 3
        self.output_df = pd.read_csv(output_df_path)
        # self.output_df = self.output_df.drop(self.output_df.columns[0], axis=1)
        self.output_df['filename'] = self.output_df['filename'].apply(lambda x: re.split(r'[/\\]', x)[-1])
        self.grade_col = grade_col

    def get_fail_pass_df(self):
        temp = self.output_df.copy()
        temp[self.grade_col+'_Grade'] = (temp[self.grade_col+'_Grade'] >= self.pass_threshold).astype(int)
        temp1 = temp.drop(['Criteria'],axis=1).groupby(['filename','Section'], as_index=False).sum()
        temp2 = temp.drop(['Criteria'],axis=1).groupby(['filename','Section'], as_index=False).size()
        self.output_df = pd.merge(temp1,temp2,on=["filename","Section"])
        self.output_df['filename'] = self.output_df['filename'].apply(lambda x: x.split('\\')[-1])
        self.output_df[f'pass_{self.grade_col}'] = (self.output_df[self.grade_col+'_Grade'] >= self.output_df['size']).astype(int)
        self.output_df = self.output_df[['filename','Section',f'pass_{self.grade_col}']]
        return self.output_df

# Class to evaluate the result performance of the AI model
class ModelResultAnalyzer():
    def __init__(self, training_result_df):
        self.training_result = training_result_df

    def calculate_mae(self,y_true, y_pred):
        # Mean Absolute Error (MAE)
        mae = np.mean(np.abs(y_true - y_pred))
        return mae
    
    def calculate_TN_rate(self,y_true,y_pred):
        true_negatives = np.sum((y_true == 0) & (y_pred == 0))
        negatives = np.sum((y_true==0))
        return true_negatives/negatives

    def plot_confusion_matrix(self,section=""):
        temp = self.training_result
        if section != "":
            temp = self.training_result[self.training_result["Section"] == section].sort_values('Real_Grade').reset_index().drop('index',axis=1)
        y_test = np.array(temp['pass_Real'])
        y_pred = np.array(temp['pass_AI'])
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred)
        recall = recall_score(y_test, y_pred)
        f1 = f1_score(y_test,y_pred)
        if section != "":
            print(f'There are {len(y_test)} {section}s in {len(y_test)} submissions')
            print(f'{len(y_test) - sum(y_test)} {section} failed')
            print(f'{sum(y_test)} {section} passed')

        print(f'Accuracy: {accuracy:.2f}')
        print(f'Precision: {precision:.2f}')
        print(f'Recall: {recall:.2f}')
        print(f'F1 score: {f1:.2f}')
        confusion_matrix = metrics.confusion_matrix(y_test, 
                                            y_pred,labels=[0, 1])
        print(confusion_matrix) 
        confusion_matrix = confusion_matrix / confusion_matrix.astype(float).sum(axis=1, keepdims=True)
        
        cm_display = metrics.ConfusionMatrixDisplay( 
            confusion_matrix=confusion_matrix, 
            display_labels=["%Fail", "%Pass"]) 
        
        im = cm_display.plot()
        im.im_.set_clim(0, 1)
        if section == "":
            plt.title(f"Confusion matrix for whole dataset")
        else:
            plt.title(f"Confusion matrix for {section}")
        plt.show()

    def get_submission_grading_accuracy(self):
        pass_training_result = self.training_result.drop(['Section'],axis=1).groupby('filename').sum().reset_index()
        pass_training_result = pass_training_result.rename(columns={'pass_AI':'AI_point','pass_Real':'Real_point'})
        pass_training_result['filename'] = pass_training_result['filename'].apply(lambda x: x.split('\\')[-1])
        pass_training_result['AI_result'] = pass_training_result['AI_point'].apply(lambda x: 'pass' if x >= 3 else 'fail')
        pass_training_result['Real_result'] = pass_training_result['Real_point'].apply(lambda x: 'pass' if x >= 3 else 'fail')

        # Compare if AI and Real results are the same
        pass_training_result['Same_result'] = pass_training_result['AI_result'] == pass_training_result['Real_result']
        result_counts = pass_training_result['Same_result'].value_counts().reindex([True, False], fill_value=0)
        print(result_counts)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

        ax1.plot(pass_training_result['filename'], pass_training_result['AI_point'], marker='o', label='AI Point', color='blue', linestyle='--')
        ax1.plot(pass_training_result['filename'], pass_training_result['Real_point'], marker='s', label='Real Point', color='green')
        ax1.set_title('AI Point vs Real Point')
        ax1.set_xlabel('Row Index')
        ax1.set_ylabel('Points')
        ax1.legend()
        ax1.grid(True)
        ax1.set_xticks(pass_training_result['filename'])
        ax1.set_xticklabels(pass_training_result['filename'], rotation=45)  # Rotate x-ticks by 45 degrees
        ax1.set_ylim(0,7)

        # --- Second plot: Same Result vs Not Same Result ---
        result_counts.plot(kind='bar', ax=ax2, color=['green', 'red'])
        ax2.set_title('Comparison of Same vs Not Same Results')
        ax2.set_xlabel('Result Match')
        ax2.set_ylabel('Count')
        ax2.set_xticks([0, 1], labels=['Same Result', 'Not Same Result'], rotation=0)
        ax2.grid(True)

        # Adjust layout
        plt.tight_layout()
        plt.show()

        return pass_training_result

    def visualize_all_sections(self):
        section_list = self.training_result['Section'].unique().tolist()
        res = pd.DataFrame({
            "Section": [],
            "Accuracy": [],
            "Precision": [],
            "Recall": [],
            "MAE": [],
            "TN_rate":[],
        })
        for section in section_list:
            temp = self.training_result[self.training_result["Section"] == section]
            y_test = np.array(temp['pass_Real'])
            y_pred = np.array(temp['pass_AI'])
            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred)
            recall = recall_score(y_test, y_pred)
            f1 = f1_score(y_test,y_pred)

            res.loc[len(res.index)] = [section,accuracy,precision,recall,self.calculate_mae(y_test,y_pred),self.calculate_TN_rate(y_test,y_pred)]
            print(f'There are {len(y_test)} {section}s in {len(y_test)} submissions')
            print(f'{len(y_test) - sum(y_test)} {section} failed')
            print(f'{sum(y_test)} {section} passed')

            print(f'Accuracy: {accuracy:.2f}')
            print(f'Precision: {precision:.2f}')
            print(f'Recall: {recall:.2f}')
            print(f'F1 score: {f1:.2f}')
            confusion_matrix = metrics.confusion_matrix(y_test, 
                                                y_pred,labels=[0,1])
            confusion_matrix = confusion_matrix / confusion_matrix.astype(float).sum(axis=1, keepdims=True)
            cm_display = metrics.ConfusionMatrixDisplay( 
                confusion_matrix=confusion_matrix, 
                display_labels=["%Fail", "%Pass"]) 
            
            im = cm_display.plot()
            im.im_.set_clim(0, 1)
            if section == "":
                plt.title(f"Confusion matrix for whole dataset")
            else:
                plt.title(f"Confusion matrix for {section}")
            plt.show()
        
        # Plotting the lines for Accuracy, Recall, and Precision
        plt.figure(figsize=(10, 6))
        plt.plot(res['Section'], res['Accuracy'], marker='o', label='Accuracy', color='blue')
        plt.plot(res['Section'], res['Recall'], marker='s', label='Recall', color='green')
        plt.plot(res['Section'], res['Precision'], marker='^', label='Precision', color='red')
        plt.plot(res['Section'], res['TN_rate'], label='True_negative_rate', color='pink')

        # Adding titles and labels
        plt.title('Accuracy, Recall, Precision, and True_Negative_Rate by Section')
        plt.xlabel('Section')
        plt.ylabel('Score')
        plt.ylim((0,1))
        plt.legend()
        plt.grid(True)

        # Show the plot
        plt.xticks(rotation=45)  # Rotate x-tick labels if needed
        plt.tight_layout()
        plt.show()